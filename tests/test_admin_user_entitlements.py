from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.services.supabase_admin import SupabaseAdminClient
from app.settings.config import Settings


def _make_supabase_admin() -> SupabaseAdminClient:
    settings = Settings(
        supabase_service_role_key="test-service-role-key",
        supabase_url="https://test.supabase.co",
        http_timeout_seconds=0.1,
    )
    return SupabaseAdminClient(settings)


@pytest.mark.asyncio
async def test_admin_user_entitlements_requires_auth(async_client):
    resp = await async_client.get("/api/v1/admin/user-entitlements", params={"user_id": "user-123"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    data = resp.json()
    assert data["status"] == status.HTTP_401_UNAUTHORIZED
    assert data["code"] == 401
    assert "request_id" in data


@pytest.mark.asyncio
async def test_admin_user_entitlements_requires_admin(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.get(
            "/api/v1/admin/user-entitlements",
            params={"user_id": "user-123"},
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["status"] == status.HTTP_403_FORBIDDEN
        assert data["code"] == 403
        assert data.get("msg") == "Admin privileges required"


@pytest.mark.asyncio
async def test_admin_user_entitlements_get_not_exists(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        supabase = _make_supabase_admin()
        supabase.fetch_one_by_user_id = AsyncMock(return_value=None)

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.get(
                "/api/v1/admin/user-entitlements",
                params={"user_id": "user-123"},
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["code"] == 200
            assert data["data"]["user_id"] == "user-123"
            assert data["data"]["exists"] is False
        finally:
            fastapi_app.state.supabase_admin = prev_client


@pytest.mark.asyncio
async def test_admin_user_entitlements_post_upsert(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        now_ms = int(time.time() * 1000)
        upsert_mock = AsyncMock(
            return_value={
                "user_id": "user-123",
                "tier": "pro",
                "expires_at": now_ms + 60_000,
                "flags": {"skip_prompt": True},
                "last_updated": now_ms,
            }
        )
        supabase = _make_supabase_admin()
        supabase.upsert_one = upsert_mock

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.post(
                "/api/v1/admin/user-entitlements",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "user_id": "user-123",
                    "tier": "pro",
                    "expires_at": now_ms + 60_000,
                    "flags": {"skip_prompt": True},
                },
            )
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["code"] == 200
            assert data["msg"] == "updated"
            assert data["data"]["user_id"] == "user-123"
            assert data["data"]["tier"] == "pro"
            assert data["data"]["flags"]["skip_prompt"] is True
            upsert_mock.assert_awaited()
        finally:
            fastapi_app.state.supabase_admin = prev_client

