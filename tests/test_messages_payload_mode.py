from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser, UserDetails
from app.services.ai_service import AIMessageInput, MessageEventBroker
from app.services.entitlement_service import EntitlementService
from app.services.llm_model_registry import ResolvedProviderRoute


def _set_active_pro_entitlement() -> EntitlementService:
    now_ms = int(time.time() * 1000)
    repo = MagicMock()
    repo.get_entitlements = AsyncMock(
        return_value={"tier": "pro", "expires_at": now_ms + 60_000, "flags": {}, "last_updated": now_ms}
    )
    return EntitlementService(repo, ttl_seconds=60)


@pytest.mark.asyncio
async def test_messages_payload_mode_requires_dialect(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = _set_active_pro_entitlement()
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "model": "global:global",
                    "payload": {"messages": [{"role": "user", "content": "hi"}]},
                },
            )
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = resp.json()
            assert data.get("code") == "dialect_required"
            assert data.get("message")
            assert data.get("request_id")
        finally:
            fastapi_app.state.entitlement_service = prev_service


@pytest.mark.asyncio
async def test_messages_payload_mode_rejects_non_allowlist_fields(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = _set_active_pro_entitlement()
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "model": "global:global",
                    "dialect": "openai.chat_completions",
                    "payload": {
                        "messages": [{"role": "user", "content": "hi"}],
                        "not_allowed": 1,
                    },
                },
            )
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = resp.json()
            assert data.get("code") == "payload_fields_not_allowed"
            assert data.get("message")
            assert data.get("request_id")
        finally:
            fastapi_app.state.entitlement_service = prev_service


@pytest.mark.asyncio
async def test_messages_payload_mode_rejects_ssot_field_conflict(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = _set_active_pro_entitlement()
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "model": "global:global",
                    "dialect": "openai.chat_completions",
                    "payload": {"messages": [{"role": "user", "content": "hi"}]},
                    "text": "should_be_rejected",
                },
            )
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = resp.json()
            assert data.get("code") == "payload_mode_conflict"
            assert data.get("message")
            assert data.get("request_id")
        finally:
            fastapi_app.state.entitlement_service = prev_service


@pytest.mark.asyncio
async def test_messages_dialect_requires_payload(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.post(
            "/api/v1/messages",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json={"model": "global:global", "dialect": "openai.chat_completions", "text": "hi"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = resp.json()
        assert data.get("code") == "payload_required"
        assert data.get("request_id")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dialect", "payload", "expected_adapter"),
    [
        ("openai.chat_completions", {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.1}, "openai.chat_completions"),
        ("openai.responses", {"input": "hi", "max_output_tokens": 32}, "openai.responses"),
        ("anthropic.messages", {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 32}, "anthropic.messages"),
        ("gemini.generate_content", {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}, "gemini.generate_content"),
    ],
)
async def test_ai_service_payload_mode_calls_expected_adapter(
    async_client,
    dialect: str,
    payload: dict,
    expected_adapter: str,
):
    ai_service = fastapi_app.state.ai_service

    dummy_route = ResolvedProviderRoute(
        endpoint={"id": 1, "base_url": "https://example.invalid", "timeout": 1},
        endpoint_id=1,
        api_key="test-api-key",
        provider="openai",
        dialect="openai.chat_completions",
        resolved_model="vendor-model",
    )

    adapters: dict[str, MagicMock] = {}
    for key in ("openai.chat_completions", "openai.responses", "anthropic.messages", "gemini.generate_content"):
        adapter = MagicMock()
        adapter.stream = AsyncMock(return_value=("ok", "{}", None, None))
        adapters[key] = adapter

    def _fake_get_adapter(d: str):
        return adapters[d]

    user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
    user_details = UserDetails(uid="user-123", email=None, display_name=None, avatar_url=None, metadata={})
    broker = MessageEventBroker()

    message = AIMessageInput(
        conversation_id="conv-123",
        model="global:global",
        dialect=dialect,
        payload=payload,
        skip_prompt=True,
        metadata={},
    )

    with patch.object(ai_service._llm_model_registry, "resolve_openai_request", new=AsyncMock(return_value=dummy_route)):
        with patch("app.services.ai_service.get_provider_adapter", side_effect=_fake_get_adapter):
            await ai_service._generate_reply(
                message_id="msg-123",
                message=message,
                user=user,
                user_details=user_details,
                broker=broker,
            )

    called = adapters[expected_adapter].stream.call_args.kwargs

    if expected_adapter == "openai.chat_completions":
        sent = called["openai_req"]
        assert sent["model"] == "vendor-model"
        assert sent["stream"] is True
        assert sent.get("temperature") == 0.1
    elif expected_adapter == "openai.responses":
        sent = called["payload"]
        assert sent["model"] == "vendor-model"
        assert sent["stream"] is True
        assert sent.get("input") == "hi"
    elif expected_adapter == "anthropic.messages":
        sent = called["payload"]
        assert sent["model"] == "vendor-model"
        assert sent["stream"] is True
        assert isinstance(sent.get("messages"), list)
    else:
        assert called["model"] == "vendor-model"
        sent = called["payload"]
        assert "model" not in sent
        assert "stream" not in sent

