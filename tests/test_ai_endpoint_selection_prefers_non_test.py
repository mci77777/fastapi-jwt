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


async def _collect_sse_events(client: AsyncClient, url: str, headers: dict[str, str], *, max_events: int = 30) -> list[dict[str, Any]]:
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


class TestAIEndpointSelectionPrefersNonTest:
    @pytest.mark.asyncio
    async def test_prefers_non_test_when_allow_test_disabled(self, async_client: AsyncClient, mock_jwt_token: str):
        request_id = "rid-non-test-preferred"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                original_allow_test = fastapi_app.state.ai_service._settings.allow_test_ai_endpoints
                fastapi_app.state.ai_service._settings.allow_test_ai_endpoints = False
                try:
                    await fastapi_app.state.ai_config_service.create_endpoint(
                        {
                            "name": "openai-real",
                            "base_url": "https://api.openai.com",
                            "api_key": "real-key",
                            "is_active": True,
                            "is_default": False,
                            "model_list": ["gpt-4o-mini"],
                        }
                    )
                    await fastapi_app.state.ai_config_service.create_endpoint(
                        {
                            "name": "测试模型",
                            "base_url": "https://tensdaq-api.x-aio.com",
                            "api_key": "test-key",
                            "is_active": True,
                            "is_default": False,
                            "model_list": ["gpt-4o-mini"],
                        }
                    )

                    mock_response = MagicMock()
                    mock_response.json.return_value = {
                        "choices": [{"message": {"content": "Hello from AI."}}],
                    }
                    mock_response.raise_for_status = MagicMock()
                    mock_response.headers = {"x-request-id": "upstream-rid"}
                    mock_httpx.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                    create = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": request_id},
                        json={"text": "Hello", "model": "gpt-4o-mini"},
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

                    call_args = mock_httpx.return_value.__aenter__.return_value.post.call_args
                    assert call_args is not None
                    called_url = call_args[0][0]
                    assert isinstance(called_url, str)
                    assert called_url.startswith("https://api.openai.com")
                finally:
                    fastapi_app.state.ai_service._settings.allow_test_ai_endpoints = original_allow_test

