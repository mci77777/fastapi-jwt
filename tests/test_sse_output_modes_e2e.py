from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.services.ai_service import MessageEvent
from scripts.monitoring.local_mock_ai_conversation_e2e import _validate_thinkingml


def _make_async_lines(lines: list[str]):
    async def gen():
        for line in lines:
            yield line

    return gen()


def _make_async_bytes(chunks: list[bytes]):
    async def gen():
        for chunk in chunks:
            yield chunk

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


def _build_valid_thinkingml_reply(*, normalize_title_variants: bool = True) -> str:
    title_open = "<Title>" if normalize_title_variants else "<title>"
    title_close = "</Title>" if normalize_title_variants else "</title>"
    return (
        "<thinking>\n"
        '<phase id="1">\n'
        f"{title_open}理解需求{title_close}\n"
        "这里提到 <final> / </final> 作为示例（应被转义为纯文本）。\n"
        "</phase>\n"
        "</thinking>\n"
        "<final>\n"
        "OK\n"
        "<!-- <serp_queries>\n"
        '["三分化训练计划怎么安排"]\n'
        "</serp_queries> -->\n"
        "</final>"
    )

def _mock_httpx_streaming_json_bytes(
    mock_httpx: MagicMock,
    *,
    json_obj: dict[str, Any],
    chunk_size: int = 32,
    headers: dict[str, str] | None = None,
) -> None:
    raw = json.dumps(json_obj, ensure_ascii=False).encode("utf-8")
    chunks = [raw[i : i + chunk_size] for i in range(0, len(raw), chunk_size)]

    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aiter_bytes = MagicMock(side_effect=lambda: _make_async_bytes(chunks))
    response.aread = AsyncMock(return_value=raw)

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


def _mock_httpx_streaming_raw_bytes(
    mock_httpx: MagicMock,
    *,
    chunks: list[bytes],
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> None:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": content_type}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aiter_bytes = MagicMock(side_effect=lambda: _make_async_bytes(chunks))
    response.aread = AsyncMock(return_value=b"".join(chunks))

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
                # 心跳默认 5s；这里给足窗口，避免误判为“没有 completed”。
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


async def _setup_openai_endpoint_mapping() -> tuple[int, str]:
    endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
        {
            "name": "openai-default",
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


@pytest.mark.asyncio
async def test_sse_xml_plaintext_streaming_contains_xml_tags(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            reply = _build_valid_thinkingml_reply(normalize_title_variants=True)
            lines = [
                f'data: {json.dumps({"choices":[{"delta":{"content":reply}}]}, ensure_ascii=False)}',
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
                        "metadata": {"result_mode": "xml_plaintext"},
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
                assert "upstream_raw" not in names

                deltas = [e["data"]["delta"] for e in events if e["event"] == "content_delta" and isinstance(e["data"], dict)]
                assert len(deltas) >= 2
                assembled = "".join(deltas)
                ok, reason = _validate_thinkingml(assembled)
                assert ok, reason
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_sse_raw_passthrough_streams_upstream_raw_frames(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            reply = _build_valid_thinkingml_reply(normalize_title_variants=False)
            lines = [
                f'data: {json.dumps({"choices":[{"delta":{"content":reply}}]}, ensure_ascii=False)}',
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
                        "result_mode": "raw_passthrough",
                        "metadata": {"result_mode": "raw_passthrough"},
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
                assert "upstream_raw" in names
                assert "completed" in names
                assert "content_delta" not in names

                raws = [e["data"].get("raw") for e in events if e["event"] == "upstream_raw" and isinstance(e["data"], dict)]
                assert len([r for r in raws if isinstance(r, str) and r]) >= 2
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_sse_xml_plaintext_non_sse_response_is_rechunked(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            reply = _build_valid_thinkingml_reply(normalize_title_variants=False) + ("\n" + ("A" * 180))
            payload = {"choices": [{"message": {"content": reply}}]}

            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_json_bytes(mock_httpx, json_obj=payload, chunk_size=25)

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={"text": "hi", "model": "gpt", "result_mode": "xml_plaintext"},
                )
                assert created.status_code == status.HTTP_202_ACCEPTED
                message_id = created.json()["message_id"]
                conversation_id = created.json()["conversation_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "Accept": "text/event-stream"},
                )

                deltas = [e for e in events if e["event"] == "content_delta"]
                assert len(deltas) > 1
                assembled = "".join(e["data"]["delta"] for e in deltas if isinstance(e["data"], dict))
                ok, reason = _validate_thinkingml(assembled)
                assert ok, reason
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_sse_raw_passthrough_non_sse_response_streams_raw_chunks(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            reply = _build_valid_thinkingml_reply(normalize_title_variants=False) + ("\n" + ("B" * 120))
            payload = {"choices": [{"message": {"content": reply}}]}

            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_json_bytes(mock_httpx, json_obj=payload, chunk_size=20)

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={"text": "hi", "model": "gpt", "result_mode": "raw_passthrough"},
                )
                assert created.status_code == status.HTTP_202_ACCEPTED
                message_id = created.json()["message_id"]
                conversation_id = created.json()["conversation_id"]

                events = await _collect_sse_events(
                    async_client,
                    f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "Accept": "text/event-stream"},
                )

                raws = [e for e in events if e["event"] == "upstream_raw"]
                assert len(raws) > 1
                assert "completed" in [e["event"] for e in events]
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_sse_auto_prefers_xml_plaintext_when_text_available(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            # 避免与其他用例共享同一 uid 导致日配额计数串扰
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-auto-xml", claims={})
            mock_get_verifier.return_value = mock_verifier

            reply = _build_valid_thinkingml_reply(normalize_title_variants=True)
            lines = [
                f'data: {json.dumps({"choices":[{"delta":{"content":reply}}]}, ensure_ascii=False)}',
                "",
                "data: [DONE]",
                "",
            ]

            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "upstream-rid"})

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-create"},
                    json={"text": "hi", "model": "gpt", "result_mode": "auto"},
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
                assert "upstream_raw" not in names

                deltas = [e["data"]["delta"] for e in events if e["event"] == "content_delta" and isinstance(e["data"], dict)]
                assert deltas
                assembled = "".join(deltas)
                ok, reason = _validate_thinkingml(assembled)
                assert ok, reason
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_sse_auto_falls_back_to_raw_passthrough_when_unparseable(async_client: AsyncClient, mock_jwt_token: str):
    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            # 避免与其他用例共享同一 uid 导致日配额计数串扰
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-auto-raw", claims={})
            mock_get_verifier.return_value = mock_verifier

            raw = b'{"choices":[{"message":{"content":"<final>OK</final>"}}'  # 故意缺失结尾括号 -> invalid JSON
            chunks = [raw[i : i + 10] for i in range(0, len(raw), 10)]
            # 确保满足 auto 的 raw 判定阈值（需要多帧）
            if len(chunks) < 6:
                chunks = chunks + [b"x"] * (6 - len(chunks))

            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_raw_bytes(mock_httpx, chunks=chunks, content_type="application/json")

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-create"},
                    json={"text": "hi", "model": "gpt", "result_mode": "auto"},
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
                assert "upstream_raw" in names
                assert "completed" in names
                assert "content_delta" not in names

                completed = next((e for e in events if e["event"] == "completed"), None)
                assert isinstance(completed, dict)
                data = completed.get("data")
                assert isinstance(data, dict)
                assert data.get("result_mode_effective") == "raw_passthrough"
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_messages_default_result_mode_without_dashboard_config_is_xml_plaintext(
    async_client: AsyncClient, mock_jwt_token: str
):
    """当客户端不传 result_mode 且 Dashboard 未配置时，应默认走 xml_plaintext（对 App 侧真流式友好）。"""

    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            # 确保没有 Dashboard 配置漂移（llm_app_settings 为空时应走默认值）
            await fastapi_app.state.sqlite_manager.execute(
                "DELETE FROM llm_app_settings WHERE key = ?",
                ("default_result_mode",),
            )

            reply = _build_valid_thinkingml_reply(normalize_title_variants=True)
            lines = [
                f'data: {json.dumps({"choices":[{"delta":{"content":reply}}]}, ensure_ascii=False)}',
                "",
                "data: [DONE]",
                "",
            ]

            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "upstream-rid"})

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-create"},
                    json={"text": "hi", "model": "gpt"},
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
                assert "upstream_raw" not in names

                deltas = [e["data"]["delta"] for e in events if e["event"] == "content_delta" and isinstance(e["data"], dict)]
                assert len(deltas) >= 2
    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_messages_default_result_mode_from_dashboard_config(async_client: AsyncClient, mock_jwt_token: str):
    """当客户端不传 result_mode 时，应使用 Dashboard 可配置的默认值（SSOT: /llm/app/config）。"""

    endpoint_id, mapping_id = await _setup_openai_endpoint_mapping()
    try:
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(
                uid="test-admin-uid",
                claims={"user_metadata": {"username": "admin", "is_admin": True}},
            )
            mock_get_verifier.return_value = mock_verifier

            updated = await async_client.post(
                "/api/v1/llm/app/config",
                headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-config"},
                json={"default_result_mode": "raw_passthrough"},
            )
            assert updated.status_code == status.HTTP_200_OK
            assert (updated.json().get("data") or {}).get("default_result_mode") == "raw_passthrough"

            reply = _build_valid_thinkingml_reply(normalize_title_variants=False)
            with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_streaming_json_bytes(
                    mock_httpx,
                    json_obj={"choices": [{"message": {"content": reply}}]},
                    chunk_size=18,
                    headers={"x-request-id": "upstream-rid"},
                )

                created = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-create"},
                    json={"text": "hi", "model": "gpt"},
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
                assert "upstream_raw" in names
                assert "content_delta" not in names
                assert "completed" in names

            restored = await async_client.post(
                "/api/v1/llm/app/config",
                headers={"Authorization": f"Bearer {mock_jwt_token}", "X-Request-Id": "rid-config-restore"},
                json={"default_result_mode": "xml_plaintext"},
            )
            assert restored.status_code == status.HTTP_200_OK

    finally:
        await _cleanup_openai_endpoint_mapping(endpoint_id, mapping_id)


@pytest.mark.asyncio
async def test_broker_rechunks_large_content_delta_into_multiple_sse_events(async_client: AsyncClient, mock_jwt_token: str):
    """即使上游/调用方一次性 publish 超长 delta，也应在 SSE 输出前拆成多帧（避免 App 侧看到“单个大 token”）。"""

    message_id = f"test-chunk-delta-{uuid.uuid4().hex}"
    conversation_id = str(uuid.uuid4())
    broker = fastapi_app.state.message_broker

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
        mock_get_verifier.return_value = mock_verifier

        await broker.create_channel(
            message_id,
            owner_user_id="test-user-123",
            conversation_id=conversation_id,
            request_id="",
            result_mode="xml_plaintext",
        )

        big = "第一行\n" + ("A" * 4096) + "\n第二行\n" + ("B" * 512)
        await broker.publish(message_id, MessageEvent(event="content_delta", data={"delta": big}))
        await broker.publish(message_id, MessageEvent(event="completed", data={"reply_len": len(big), "reply": big}))
        await broker.close(message_id)

        events = await _collect_sse_events(
            async_client,
            f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
            headers={"Authorization": f"Bearer {mock_jwt_token}", "Accept": "text/event-stream"},
            max_events=400,
        )

        deltas = [e["data"]["delta"] for e in events if e["event"] == "content_delta" and isinstance(e.get("data"), dict)]
        assert len(deltas) > 1
        assert "".join(deltas) == big


@pytest.mark.asyncio
async def test_broker_rechunks_large_upstream_raw_into_multiple_sse_events(async_client: AsyncClient, mock_jwt_token: str):
    """raw_passthrough 下，超长 upstream_raw 也应拆分输出，避免单帧过大导致“看起来不流式”。"""

    message_id = f"test-chunk-raw-{uuid.uuid4().hex}"
    conversation_id = str(uuid.uuid4())
    broker = fastapi_app.state.message_broker

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
        mock_get_verifier.return_value = mock_verifier

        await broker.create_channel(
            message_id,
            owner_user_id="test-user-123",
            conversation_id=conversation_id,
            request_id="",
            result_mode="raw_passthrough",
        )

        big_raw = "event:message\n" + ("X" * 4096) + "\n"
        await broker.publish(
            message_id,
            MessageEvent(
                event="upstream_raw",
                data={"dialect": "openai.chat_completions", "upstream_event": "message", "raw": big_raw},
            ),
        )
        await broker.publish(message_id, MessageEvent(event="completed", data={"reply_len": 0}))
        await broker.close(message_id)

        events = await _collect_sse_events(
            async_client,
            f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
            headers={"Authorization": f"Bearer {mock_jwt_token}", "Accept": "text/event-stream"},
            max_events=400,
        )

        raws = [e["data"]["raw"] for e in events if e["event"] == "upstream_raw" and isinstance(e.get("data"), dict)]
        assert len(raws) > 1
        assert "".join(raws) == big_raw
