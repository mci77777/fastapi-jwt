from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth import AuthenticatedUser, ProviderError


def _mock_httpx_stream_json(mock_httpx: MagicMock, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aread = AsyncMock(return_value=json.dumps(payload).encode("utf-8"))

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


async def _collect_sse_events(client: AsyncClient, url: str, headers: dict[str, str], *, max_events: int = 50) -> list[dict[str, Any]]:
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
        for _ in range(max_events * 6):  # 每个事件最多几行
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


class TestRequestIdSSOT:
    @pytest.mark.asyncio
    async def test_401_contains_request_id(self, async_client: AsyncClient):
        request_id = "rid-422-test"
        response = await async_client.post(
            "/api/v1/messages",
            headers={"X-Request-Id": request_id},
            json={"text": "hi"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        body = response.json()
        assert body.get("request_id") == request_id
        assert response.headers.get("x-request-id") == request_id

    @pytest.mark.asyncio
    async def test_422_model_not_allowed_contains_request_id(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-model-not-allowed"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            response = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                json={"text": "hi", "model": "invalid:does-not-exist"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        if isinstance(body, dict) and isinstance(body.get("detail"), dict):
            detail = body["detail"]
            assert detail.get("code") == "model_not_allowed"
            assert detail.get("request_id") == request_id
        else:
            assert isinstance(body, dict)
            assert body.get("code") == "model_not_allowed"
            assert body.get("request_id") == request_id
        assert response.headers.get("x-request-id") == request_id

    @pytest.mark.asyncio
    async def test_openai_forwarding_and_sse_success(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-openai-sse"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini"],
                    }
                )

                _mock_httpx_stream_json(
                    mock_httpx,
                    {"choices": [{"message": {"content": "Hello from AI."}}]},
                    headers={"x-request-id": "upstream-rid"},
                )

                create = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                    json={
                        "text": "Hello",
                        "model": "global:global",
                        "result_mode": "xml_plaintext",
                        "system_prompt": "You are a helpful assistant.",
                        "tools": [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object"}}}],
                        "tool_choice": "auto",
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "max_tokens": 32,
                        "metadata": {"client": "pytest"},
                    },
                )

                assert create.status_code == status.HTTP_202_ACCEPTED
                assert create.headers.get("x-request-id") == request_id
                message_id = create.json()["message_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events",
                    headers={
                        "Authorization": f"Bearer {mock_jwt_token}",
                        "Accept": "text/event-stream",
                        "X-Request-Id": request_id,
                    },
                )

                event_names = [item["event"] for item in events]
                assert "content_delta" in event_names
                assert "completed" in event_names

                # 验证上游转发：仅 OpenAI 语义字段 + 透传 request_id header
                call_args = mock_httpx.return_value.__aenter__.return_value.stream.call_args
                assert call_args is not None
                upstream_headers = call_args[1]["headers"]
                assert upstream_headers.get("X-Request-Id") == request_id
                upstream_payload = call_args[1]["json"]
                assert set(upstream_payload.keys()).issubset(
                    {"model", "messages", "tools", "tool_choice", "temperature", "top_p", "max_tokens", "stream"}
                )

    @pytest.mark.asyncio
    async def test_openai_tool_calls_without_executor_returns_clear_error(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-openai-tool-calls"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini"],
                    }
                )

                # 为本用例创建一个“映射模型”，并让其解析到 gpt-4o-mini
                mapping_id = "tenant:toolcalls-test"
                await fastapi_app.state.model_mapping_service.upsert_mapping(
                    {
                        "scope_type": "tenant",
                        "scope_key": "toolcalls-test",
                        "name": "toolcalls-test",
                        "default_model": "gpt-4o-mini",
                        "candidates": ["gpt-4o-mini"],
                        "is_active": True,
                        "metadata": {},
                    }
                )

                _mock_httpx_stream_json(
                    mock_httpx,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {"id": "call_1", "type": "function", "function": {"name": "noop", "arguments": "{}"}}
                                    ],
                                }
                            }
                        ]
                    },
                    headers={"x-request-id": "upstream-rid"},
                )

                create = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                    json={
                        "text": "Hello",
                        "model": mapping_id,
                        "result_mode": "xml_plaintext",
                        "tools": [{"type": "function", "function": {"name": "noop"}}],
                        "tool_choice": "auto",
                    },
                )
                assert create.status_code == status.HTTP_202_ACCEPTED
                message_id = create.json()["message_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events",
                    headers={
                        "Authorization": f"Bearer {mock_jwt_token}",
                        "Accept": "text/event-stream",
                        "X-Request-Id": request_id,
                    },
                )

                assert any(item["event"] == "error" for item in events)
                last_error = next(item for item in reversed(events) if item["event"] == "error")
                assert isinstance(last_error["data"], dict)
                assert last_error["data"].get("request_id") == request_id
                assert "tool_calls_not_supported" in str(last_error["data"].get("error") or "")

                await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)

    @pytest.mark.asyncio
    async def test_claude_headers_compliance(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-claude-success"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "claude-upstream",
                        "base_url": "https://api.anthropic.com",
                        "api_key": "test-claude-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["claude-3-5-sonnet-20240620"],
                    }
                )

                # 为本用例创建一个可路由到 Claude 的“映射模型”（避免依赖 global:global 的既有候选）
                mapping_id = "tenant:claude-test"
                await fastapi_app.state.model_mapping_service.upsert_mapping(
                    {
                        "scope_type": "tenant",
                        "scope_key": "claude-test",
                        "name": "claude-test",
                        "default_model": "claude-3-5-sonnet-20240620",
                        "candidates": ["claude-3-5-sonnet-20240620"],
                        "is_active": True,
                        "metadata": {},
                    }
                )

                _mock_httpx_stream_json(
                    mock_httpx,
                    {"content": [{"type": "text", "text": "Hello from Claude."}]},
                    headers={"request-id": "anthropic-request-id"},
                )

                create = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                    json={
                        "text": "Hello",
                        "model": mapping_id,
                        "metadata": {"client": "pytest"},
                    },
                )
                assert create.status_code == status.HTTP_202_ACCEPTED
                message_id = create.json()["message_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events",
                    headers={
                        "Authorization": f"Bearer {mock_jwt_token}",
                        "Accept": "text/event-stream",
                        "X-Request-Id": request_id,
                    },
                )

                assert any(item["event"] == "completed" for item in events)

                # Claude header 合规断言：必须 x-api-key + anthropic-version，不默认 anthropic-beta
                call_args = mock_httpx.return_value.__aenter__.return_value.stream.call_args
                assert call_args is not None
                hdr = call_args[1]["headers"]
                assert hdr.get("x-api-key") == "test-claude-key"
                assert hdr.get("anthropic-version") == "2023-06-01"
                assert "anthropic-beta" not in {k.lower() for k in hdr.keys()}

                await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)

    @pytest.mark.asyncio
    async def test_sse_error_contains_request_id_and_terminates(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-provider-error"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch.object(
                fastapi_app.state.ai_service,
                "_call_openai_chat_completions_streaming",
                new=AsyncMock(side_effect=ProviderError("forced_provider_error")),
            ):
                create = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                    json={"text": "Hello", "model": "global:global"},
                )
                assert create.status_code == status.HTTP_202_ACCEPTED
                message_id = create.json()["message_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events",
                    headers={
                        "Authorization": f"Bearer {mock_jwt_token}",
                        "Accept": "text/event-stream",
                        "X-Request-Id": request_id,
                    },
                )

                assert any(item["event"] == "error" for item in events)
                last_error = next(item for item in reversed(events) if item["event"] == "error")
                assert isinstance(last_error["data"], dict)
                assert last_error["data"].get("request_id") == request_id
