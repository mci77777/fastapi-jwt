from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.services.entitlement_service import EntitlementService


@pytest.mark.asyncio
async def test_messages_skip_prompt_denied_for_anonymous(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="anon-user-123", claims={}, user_type="anonymous")
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.post(
            "/api/v1/messages",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json={"text": "Hello", "skip_prompt": True},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "entitlement_required"


@pytest.mark.asyncio
async def test_messages_skip_prompt_denied_without_entitlement(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        repo = MagicMock()
        repo.get_entitlements = AsyncMock(return_value=None)
        service = EntitlementService(repo, ttl_seconds=60)

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = service
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"text": "Hello", "skip_prompt": True},
            )
            assert resp.status_code == status.HTTP_403_FORBIDDEN
            data = resp.json()
            assert data["code"] == "entitlement_required"
        finally:
            fastapi_app.state.entitlement_service = prev_service


@pytest.mark.asyncio
async def test_messages_skip_prompt_denied_for_expired_pro(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        now_ms = int(time.time() * 1000)
        repo = MagicMock()
        repo.get_entitlements = AsyncMock(
            return_value={"tier": "pro", "expires_at": now_ms - 60_000, "flags": {}, "last_updated": now_ms - 60_000}
        )
        service = EntitlementService(repo, ttl_seconds=60)

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = service
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"text": "Hello", "skip_prompt": True},
            )
            assert resp.status_code == status.HTTP_403_FORBIDDEN
            data = resp.json()
            assert data["code"] == "entitlement_required"
        finally:
            fastapi_app.state.entitlement_service = prev_service


@pytest.mark.asyncio
async def test_messages_skip_prompt_allowed_for_active_pro(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        now_ms = int(time.time() * 1000)
        repo = MagicMock()
        repo.get_entitlements = AsyncMock(
            return_value={"tier": "pro", "expires_at": now_ms + 60_000, "flags": {}, "last_updated": now_ms}
        )
        service = EntitlementService(repo, ttl_seconds=60)

        prev_service = getattr(fastapi_app.state, "entitlement_service", None)
        fastapi_app.state.entitlement_service = service
        try:
            resp = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"text": "Hello", "skip_prompt": True, "model": "global:global"},
            )
            assert resp.status_code == status.HTTP_202_ACCEPTED
            data = resp.json()
            assert "message_id" in data
        finally:
            fastapi_app.state.entitlement_service = prev_service

