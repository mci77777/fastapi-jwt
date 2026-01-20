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


def _admin_user(uid: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        uid=uid,
        claims={
            "sub": uid,
            "user_metadata": {"username": "admin", "is_admin": True},
        },
    )


def _make_async_lines(lines: list[str]):
    async def gen():
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
    client: AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    max_events: int = 200,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", url, headers=headers, timeout=30.0) as response:
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
        for _ in range(max_events * 8):
            try:
                line = await asyncio.wait_for(lines_iter.__anext__(), timeout=8.0)
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


def _assert_jsonseq_v1_sequence(events: list[dict[str, Any]]) -> None:
    allowed = {
        "serp_summary",
        "thinking_start",
        "phase_start",
        "phase_delta",
        "thinking_end",
        "final_delta",
        "serp_queries",
        "final_end",
    }
    seq = [e for e in events if e.get("event") in allowed]
    names = [e.get("event") for e in seq]
    assert "thinking_start" in names
    assert "thinking_end" in names
    assert "final_delta" in names
    assert "final_end" in names

    # 顺序：thinking_end 在 final_delta 之前
    assert names.index("thinking_end") < names.index("final_delta")

    # phase_start 必须递增且包含 title；phase_delta 必须引用已开始的 phase
    current_phase_id = 0
    for item in seq:
        ev = item.get("event")
        data = item.get("data")
        if ev == "phase_start":
            assert isinstance(data, dict)
            pid = int(data.get("id"))
            title = str(data.get("title") or "").strip()
            assert pid == current_phase_id + 1
            assert title
            current_phase_id = pid
        if ev == "phase_delta":
            assert isinstance(data, dict)
            pid = int(data.get("id"))
            text = str(data.get("text") or "")
            assert pid >= 1 and pid <= current_phase_id
            assert text

    # serp_queries（若出现）必须是数组
    for item in seq:
        if item.get("event") != "serp_queries":
            continue
        data = item.get("data")
        assert isinstance(data, dict)
        queries = data.get("queries")
        assert isinstance(queries, list)


async def _setup_openai_endpoint_mapping() -> tuple[int, str]:
    endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
        {
            "name": "openai-default-jsonseq",
            "base_url": "https://api.openai.com",
            "api_key": "test-api-key",
            "is_active": True,
            "is_default": False,
            "model_list": ["gpt-4o-mini"],
        }
    )
    endpoint_id = int(endpoint.get("id"))

    mapping_id = "mapping:gpt"
    await fastapi_app.state.model_mapping_service.upsert_mapping(
        {
            "scope_type": "mapping",
            "scope_key": "gpt",
            "name": "gpt",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "metadata": {},
        }
    )
    return endpoint_id, mapping_id


async def _cleanup_openai_endpoint_mapping(endpoint_id: int | None, mapping_id: str | None) -> None:
    if mapping_id:
        try:
            await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)
        except Exception:
            pass
    if endpoint_id is not None:
        try:
            await fastapi_app.state.ai_config_service.delete_endpoint(int(endpoint_id), sync_remote=False)
        except Exception:
            pass


def _build_valid_thinkingml_reply() -> str:
    return (
        "<serp>用户要一份三分化训练方案。</serp>\n"
        "<thinking>\n"
        '<phase id=\"1\">\\n'
        "<Title>需求拆解</Title>\\n"
        "这里提到 <final> / </final> 作为示例（应被转义为纯文本）。\\n"
        "</phase>\\n"
        "</thinking>\\n"
        "<final>\\n"
        "# OK\\n"
        "<!-- <serp_queries>\\n"
        '[\"三分化训练计划怎么安排\",\"三分化训练动作选择\"]\\n'
        "</serp_queries> -->\\n"
        "</final>"
    )


@pytest.mark.asyncio
async def test_sse_jsonseq_v1_emits_unified_events(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = _admin_user("test-user-jsonseq-v1")
            mock_get_verifier.return_value = mock_verifier
            try:
                # 开启 JSONSeq v1（Dashboard 配置）
                resp = await async_client.post(
                    "/api/v1/llm/app/config",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={"app_output_protocol": "jsonseq_v1"},
                )
                assert resp.status_code == status.HTTP_200_OK

                reply = _build_valid_thinkingml_reply()
                lines = [
                    f"data: {json.dumps({'choices': [{'delta': {'content': reply}}]}, ensure_ascii=False)}",
                    "",
                    "data: [DONE]",
                    "",
                ]

                with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                    _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "upstream-rid"})

                    created = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-create"},
                        json={
                            "text": "hi",
                            "model": "gpt",
                            "result_mode": "xml_plaintext",
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
                    assert "content_delta" not in names
                    assert "completed" in names

                    _assert_jsonseq_v1_sequence(events)
            finally:
                # 恢复默认协议，避免影响后续 SSE 用例（测试间共享同一 SQLite）。
                await async_client.post(
                    "/api/v1/llm/app/config",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={"app_output_protocol": "thinkingml_v45"},
                )
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)
