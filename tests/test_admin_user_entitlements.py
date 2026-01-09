from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.db import get_sqlite_manager
from app.services.supabase_admin import SupabaseAdminClient
from app.services.supabase_admin import SupabaseAdminError
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
async def test_admin_user_entitlements_supabase_error_returns_diagnostic(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        supabase = _make_supabase_admin()
        supabase.fetch_one_by_user_id = AsyncMock(
            side_effect=SupabaseAdminError(
                code="supabase_request_failed",
                message="Supabase request failed",
                status_code=404,
                hint="检查 Supabase 是否已创建表 user_entitlements",
            )
        )

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.get(
                "/api/v1/admin/user-entitlements",
                params={"user_id": "user-123"},
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert resp.status_code == 404
            data = resp.json()
            assert data["status"] == 404
            assert data["code"] == "supabase_request_failed"
            assert "msg" in data and "user_entitlements" in data["msg"]
            assert "request_id" in data
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


@pytest.mark.asyncio
async def test_admin_user_entitlements_stats(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        async def _count_rows(*, table: str, filters=None):
            if table == "user_entitlements":
                if not filters:
                    return 10
                if filters.get("tier") == "eq.free":
                    return 6
                if filters.get("tier") == "eq.pro" and "or" not in filters:
                    return 3
                if filters.get("tier") == "eq.pro" and "or" in filters:
                    return 2
                return 1
            if table == "users":
                if filters and filters.get("isanonymous") == "eq.1":
                    return 4
                return 0
            raise AssertionError(f"unexpected table={table}")

        supabase = _make_supabase_admin()
        supabase.count_rows = AsyncMock(side_effect=_count_rows)

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.get(
                "/api/v1/admin/user-entitlements/stats",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            payload = resp.json()
            assert payload["code"] == 200
            data = payload["data"]
            assert data["total_rows"] == 10
            assert data["pro_active"] == 2
            assert data["pro_expired"] == 1
            assert data["anonymous_users"] == 4
            tiers = {item["tier"]: item["count"] for item in data["tiers"]}
            assert tiers["free"] == 6
            assert tiers["pro"] == 3
            assert tiers["other"] == 1
        finally:
            fastapi_app.state.supabase_admin = prev_client


@pytest.mark.asyncio
async def test_admin_user_entitlements_list(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        now_ms = int(time.time() * 1000)
        supabase = _make_supabase_admin()
        fetch_list_mock = AsyncMock(
            return_value=(
                [
                    {
                        "user_id": "user-123",
                        "tier": "pro",
                        "expires_at": now_ms + 60_000,
                        "flags": {"skip_prompt": True},
                        "last_updated": now_ms,
                        "exists": True,
                        "is_anonymous": False,
                    }
                ],
                1,
            )
        )
        supabase.fetch_list = fetch_list_mock

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.get(
                "/api/v1/admin/user-entitlements/list",
                params={"page": 1, "page_size": 20, "tier": "pro"},
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            payload = resp.json()
            assert payload["code"] == 200
            data = payload["data"]
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["user_id"] == "user-123"
            assert data["items"][0]["tier"] == "pro"
            fetch_list_mock.assert_awaited()
            _, kwargs = fetch_list_mock.await_args
            assert kwargs["table"] == "user_entitlements_list"
        finally:
            fastapi_app.state.supabase_admin = prev_client


@pytest.mark.asyncio
async def test_admin_user_entitlements_presets_default(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        db = get_sqlite_manager(fastapi_app)
        await db.execute("DELETE FROM user_entitlement_tier_presets", ())

        resp = await async_client.get(
            "/api/v1/admin/user-entitlements/presets",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert payload["code"] == 200
        presets = payload["data"]
        tiers = {item["tier"]: item for item in presets}
        assert "free" in tiers
        assert "pro" in tiers
        assert tiers["pro"]["default_expires_days"] == 30


@pytest.mark.asyncio
async def test_admin_user_entitlements_presets_upsert_and_delete(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        db = get_sqlite_manager(fastapi_app)
        await db.execute("DELETE FROM user_entitlement_tier_presets", ())

        resp = await async_client.post(
            "/api/v1/admin/user-entitlements/presets",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json={"tier": "vip", "default_expires_days": 7, "flags": {"skip_prompt": True}},
        )
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert payload["code"] == 200
        assert payload["data"]["tier"] == "vip"
        assert payload["data"]["default_expires_days"] == 7

        resp = await async_client.get(
            "/api/v1/admin/user-entitlements/presets",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        presets = resp.json()["data"]
        tiers = {item["tier"] for item in presets}
        assert {"free", "pro", "vip"} <= tiers

        resp = await async_client.delete(
            "/api/v1/admin/user-entitlements/presets/vip",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert payload["code"] == 200
        assert payload["msg"] == "deleted"

        resp = await async_client.get(
            "/api/v1/admin/user-entitlements/presets",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        presets = resp.json()["data"]
        tiers = {item["tier"] for item in presets}
        assert "vip" not in tiers
