from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.services.entitlement_service import EntitlementService


def _make_async_lines(lines: list[str]) -> AsyncIterator[str]:
    async def gen() -> AsyncIterator[str]:
        for line in lines:
            yield line

    return gen()


def _mock_httpx_streaming_sse(mock_httpx: MagicMock, *, lines: list[str], headers: dict[str, str] | None = None) -> None:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/event-stream"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aiter_lines = MagicMock(side_effect=lambda: _make_async_lines(lines))
    response.aread = AsyncMock(return_value=b"")

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


async def _collect_sse_events(
    client,
    url: str,
    headers: dict[str, str],
    *,
    max_events: int = 80,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", url, headers=headers, timeout=10.0) as response:
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


def _set_active_pro_entitlement() -> EntitlementService:
    now_ms = int(time.time() * 1000)
    repo = MagicMock()
    repo.get_entitlements = AsyncMock(
        return_value={"tier": "pro", "expires_at": now_ms + 60_000, "flags": {}, "last_updated": now_ms}
    )
    return EntitlementService(repo, ttl_seconds=60)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dialect", "payload", "patch_target", "lines"),
    [
        (
            "openai.chat_completions",
            {"messages": [{"role": "user", "content": "hi"}]},
            "app.services.providers.openai_chat_completions.httpx.AsyncClient",
            [
                'data: {"choices":[{"delta":{"content":"Hi"}}]}',
                "",
                "data: [DONE]",
                "",
            ],
        ),
        (
            "openai.responses",
            {"input": "hi", "max_output_tokens": 16},
            "app.services.providers.openai_responses.httpx.AsyncClient",
            [
                'data: {"type":"response.output_text.delta","delta":"Hi"}',
                "",
                'data: {"type":"response.completed"}',
                "",
            ],
        ),
        (
            "anthropic.messages",
            {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
            "app.services.providers.anthropic_messages.httpx.AsyncClient",
            [
                "event: content_block_delta",
                'data: {"delta":{"type":"text_delta","text":"Hi"}}',
                "",
                "event: message_stop",
                "data: {}",
                "",
            ],
        ),
        (
            "gemini.generate_content",
            {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            "app.services.providers.gemini_generate_content.httpx.AsyncClient",
            [
                'data: {"candidates":[{"content":{"parts":[{"text":"Hi"}]}}]}',
                "",
                "data: [DONE]",
                "",
            ],
        ),
    ],
)
async def test_payload_mode_4_dialects_smoke(async_client, mock_jwt_token: str, dialect, payload, patch_target, lines):
    prev_service = getattr(fastapi_app.state, "entitlement_service", None)
    fastapi_app.state.entitlement_service = _set_active_pro_entitlement()

    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
            mock_get_verifier.return_value = mock_verifier

            models = await async_client.get(
                "/api/v1/llm/models?view=mapped",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert models.status_code == status.HTTP_200_OK
            model_list = (models.json() or {}).get("data") or []
            assert isinstance(model_list, list) and model_list
            model_key = str((model_list[0] or {}).get("name") or "").strip()
            assert model_key

            with patch(patch_target) as mock_httpx:
                _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "upstream"})

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": f"rid-{dialect}"},
                    json={
                        "model": model_key,
                        "dialect": dialect,
                        "payload": payload,
                        "result_mode": "xml_plaintext",
                        "metadata": {"save_history": False, "client": "pytest"},
                    },
                )
                assert created.status_code == status.HTTP_202_ACCEPTED
                message_id = created.json()["message_id"]
                conversation_id = created.json()["conversation_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "Accept": "text/event-stream"},
                )

                names = [e["event"] for e in events]
                assert "content_delta" in names
                assert "completed" in names
    finally:
        fastapi_app.state.entitlement_service = prev_service
