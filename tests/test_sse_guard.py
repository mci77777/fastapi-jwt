from __future__ import annotations

import json
import uuid

import pytest
from starlette.requests import Request

from app.auth import AuthenticatedUser
from app.core.sse_guard import check_sse_concurrency, get_sse_guard, unregister_sse_connection


def _make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/messages/mock/events",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "query_string": b"",
        }
    )


def _reset_guard_state() -> None:
    guard = get_sse_guard()
    guard.active_connections.clear()
    guard.user_connections.clear()
    guard.conversation_connections.clear()
    guard.total_connections_created = 0
    guard.total_connections_rejected = 0
    guard.rejection_reasons.clear()


class TestSseGuard:
    @pytest.mark.asyncio
    async def test_check_sse_concurrency_rejects_second_connection_for_same_conversation(self):
        _reset_guard_state()
        guard = get_sse_guard()

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        conversation_id = str(uuid.uuid4())
        request = _make_request()

        # 第一条连接允许
        r1 = await check_sse_concurrency("c1", user, conversation_id, "m1", request)
        assert r1 is None

        # 第二条同 conversation 连接应拒绝：429 + stable code + Retry-After
        r2 = await check_sse_concurrency("c2", user, conversation_id, "m2", request)
        assert r2 is not None
        assert r2.status_code == 429
        assert r2.headers.get("Retry-After")

        payload = json.loads(r2.body.decode("utf-8"))
        assert payload.get("code") == "SSE_CONCURRENCY_LIMIT_EXCEEDED"
        assert payload.get("request_id")

        await unregister_sse_connection("c1")

        stats = await guard.get_stats()
        assert stats["active_connections"] == 0

