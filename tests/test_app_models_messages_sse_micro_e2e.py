from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth import AuthenticatedUser


async def _collect_sse_events(
    client: AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    max_events: int = 50,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", url, headers=headers, timeout=5.0) as response:
        assert response.status_code == status.HTTP_200_OK

        current_event = "message"
        data_lines: list[str] = []

        async def flush() -> None:
            nonlocal current_event, data_lines
            if not data_lines:
                current_event = "message"
                return
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            events.append({"event": current_event, "data": parsed})
            current_event = "message"

        lines_iter = response.aiter_lines()
        for _ in range(max_events * 6):
            try:
                line = await asyncio.wait_for(lines_iter.__anext__(), timeout=2.0)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                break

            if line is None:
                break
            line = line.rstrip("\r")
            if not line:
                await flush()
                if events and events[-1]["event"] in {"completed", "error"}:
                    break
                continue

            if line.startswith("event:"):
                current_event = line[len("event:") :].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())

        await flush()

    return events


class TestAppModelsMicroE2E:
    @pytest.mark.asyncio
    async def test_models_to_messages_to_sse_with_business_model_key(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id_create = "rid-app-create"
        request_id_sse = "rid-app-sse"

        created_endpoint_id = None
        mapping_id = "tenant:xai"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                # 准备：可路由 endpoint + 映射（业务 key=xai → grok-4）
                endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "xai-default",
                        "base_url": "https://api.x.ai",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": False,
                        "model_list": ["grok-4"],
                    }
                )
                created_endpoint_id = endpoint.get("id")

                await fastapi_app.state.model_mapping_service.upsert_mapping(
                    {
                        "scope_type": "tenant",
                        "scope_key": "xai",
                        "name": "xai",
                        "default_model": "grok-4",
                        "candidates": ["grok-4"],
                        "is_active": True,
                        "metadata": {},
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {"choices": [{"message": {"content": "Hello from xAI."}}]}
                mock_response.raise_for_status = MagicMock()
                mock_response.headers = {"x-request-id": "upstream-rid"}
                mock_httpx.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                try:
                    # 1) 拉取模型列表：name 为业务 key
                    models = await async_client.get(
                        "/api/v1/llm/models?only_active=true&page=1&page_size=100",
                        headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    )
                    assert models.status_code == status.HTTP_200_OK
                    payload = models.json()
                    assert payload.get("code") == 200
                    data = payload.get("data") or []
                    picked = next(item for item in data if item.get("name") == "xai")
                    assert set(picked.keys()).issuperset({"name", "default_model", "candidates"})

                    # 2) 创建消息：model=业务 key（与 metadata.model 一致）
                    create = await async_client.post(
                        "/api/v1/messages",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "X-Request-Id": request_id_create,
                        },
                        json={
                            "text": "hi",
                            "conversation_id": None,
                            "metadata": {"client_message_id": "msg_HNXN78", "model": "xai"},
                            "skip_prompt": False,
                            "model": "xai",
                            "messages": None,
                            "system_prompt": "You are GymBro's AI assistant.",
                            "tools": None,
                            "tool_choice": "auto",
                            "temperature": 0.7,
                            "top_p": None,
                            "max_tokens": 32,
                        },
                    )
                    assert create.status_code == status.HTTP_202_ACCEPTED
                    message_id = create.json()["message_id"]
                    conversation_id = create.json()["conversation_id"]

                    # 3) SSE 拉流：与 create 使用不同 request_id（App 实际行为）
                    events = await _collect_sse_events(
                        async_client,
                        f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "Accept": "text/event-stream",
                            "X-Request-Id": request_id_sse,
                        },
                    )
                    event_names = [item["event"] for item in events]
                    assert "content_delta" in event_names
                    assert "completed" in event_names

                    # 上游 payload.model 必须是 resolved vendor model（不能是业务 key）
                    call_args = mock_httpx.return_value.__aenter__.return_value.post.call_args
                    assert call_args is not None
                    upstream_payload = call_args[1]["json"]
                    assert upstream_payload.get("model") == "grok-4"
                finally:
                    # cleanup：避免跨用例漂移
                    try:
                        await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)
                    except Exception:
                        pass
                    if created_endpoint_id is not None:
                        try:
                            await fastapi_app.state.ai_config_service.delete_endpoint(int(created_endpoint_id), sync_remote=False)
                        except Exception:
                            pass
