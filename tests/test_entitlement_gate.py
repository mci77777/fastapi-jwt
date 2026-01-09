from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser


@pytest.mark.asyncio
async def test_messages_payload_mode_allowed_for_anonymous(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="anon-user-123", claims={}, user_type="anonymous")
        mock_get_verifier.return_value = mock_verifier

        with patch.object(fastapi_app.state.ai_service, "run_conversation", new=AsyncMock(return_value=None)):
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "model": "global:global",
                    "dialect": "openai.chat_completions",
                    "payload": {"messages": [{"role": "user", "content": "hi"}]},
                },
            )
            assert resp.status_code == status.HTTP_202_ACCEPTED
            data = resp.json()
            assert data.get("message_id")


@pytest.mark.asyncio
async def test_messages_payload_mode_requires_dialect(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="anon-user-456", claims={}, user_type="anonymous")
        mock_get_verifier.return_value = mock_verifier

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


@pytest.mark.asyncio
async def test_messages_model_daily_quota_exceeded_for_free_user(async_client, mock_jwt_token: str, monkeypatch):
    # isolate bucket: map any requested model to "xai", and set a tiny daily limit
    from app.api.v1 import messages as messages_module

    monkeypatch.setattr(messages_module, "_normalize_quota_model_key", lambda _model: "xai")
    monkeypatch.setattr(messages_module, "_FREE_TIER_DAILY_MODEL_LIMITS", {"xai": 2, "deepseek": None, "gpt": 20, "claude": 20, "gemini": 20})

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="quota-user-123", claims={}, user_type="anonymous")
        mock_get_verifier.return_value = mock_verifier

        with patch.object(fastapi_app.state.ai_service, "run_conversation", new=AsyncMock(return_value=None)):
            for _ in range(2):
                resp = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={
                        "model": "global:global",
                        "dialect": "openai.chat_completions",
                        "payload": {"messages": [{"role": "user", "content": "hi"}]},
                        "metadata": {"client": "pytest"},
                    },
                )
                assert resp.status_code == status.HTTP_202_ACCEPTED

            blocked = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "model": "global:global",
                    "dialect": "openai.chat_completions",
                    "payload": {"messages": [{"role": "user", "content": "hi"}]},
                    "metadata": {"client": "pytest"},
                },
            )
            assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            data = blocked.json()
            assert data.get("code") == "model_daily_quota_exceeded"

