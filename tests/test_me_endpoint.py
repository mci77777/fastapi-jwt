from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.repositories.user_repo import UserRepository


@pytest.mark.asyncio
async def test_v1_me_requires_auth(async_client):
    resp = await async_client.get("/v1/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    data = resp.json()
    assert data["status"] == status.HTTP_401_UNAUTHORIZED
    assert data["code"] == "unauthorized"
    assert "request_id" in data


@pytest.mark.asyncio
async def test_v1_me_anonymous_minimal(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="anon-user-123", claims={}, user_type="anonymous")
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {mock_jwt_token}"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["uid"] == "anon-user-123"
        assert data["user_type"] == "anonymous"
        assert isinstance(data["server_time"], str) and "T" in data["server_time"]
        assert data.get("profile") is None
        assert data.get("settings") is None
        assert data.get("entitlements") is None


@pytest.mark.asyncio
async def test_v1_me_permanent_aggregates_user_bundle(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        now_ms = int(time.time() * 1000)

        async def _fetch_one_by_user_id(*, table: str, user_id: str):
            assert user_id == "user-123"
            if table == "user_profiles":
                return {"display_name": "Test", "bio": "Hello", "last_updated": now_ms, "ignored": "x"}
            if table == "user_settings":
                return {"theme_mode": "dark", "ai_memory_enabled": True, "last_updated": now_ms, "ignored": "x"}
            if table == "user_entitlements":
                return {
                    "tier": "pro",
                    "expires_at": now_ms + 60_000,
                    "flags": {"skip_prompt": True},
                    "last_updated": now_ms,
                    "ignored": "x",
                }
            return None

        mock_supabase = MagicMock()
        mock_supabase.fetch_one_by_user_id = AsyncMock(side_effect=_fetch_one_by_user_id)
        repo = UserRepository(mock_supabase)

        prev_repo = getattr(fastapi_app.state, "user_repository", None)
        fastapi_app.state.user_repository = repo
        try:
            resp = await async_client.get("/v1/me", headers={"Authorization": f"Bearer {mock_jwt_token}"})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["uid"] == "user-123"
            assert data["user_type"] == "permanent"
            assert isinstance(data["server_time"], str) and "T" in data["server_time"]

            assert data["profile"]["display_name"] == "Test"
            assert "ignored" not in data["profile"]

            assert data["settings"]["theme_mode"] == "dark"
            assert "ignored" not in data["settings"]

            assert data["entitlements"]["tier"] == "pro"
            assert data["entitlements"]["flags"]["skip_prompt"] is True
            assert "ignored" not in data["entitlements"]
        finally:
            fastapi_app.state.user_repository = prev_repo

