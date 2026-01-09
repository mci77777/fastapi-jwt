from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.db import get_sqlite_manager
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
async def test_admin_app_users_requires_auth(async_client):
    resp = await async_client.get("/api/v1/admin/app-users/list")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    data = resp.json()
    assert data["status"] == status.HTTP_401_UNAUTHORIZED
    assert data["code"] == 401
    assert "request_id" in data


@pytest.mark.asyncio
async def test_admin_app_users_requires_admin(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.get(
            "/api/v1/admin/app-users/list",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["status"] == status.HTTP_403_FORBIDDEN
        assert data["code"] == 403
        assert data.get("msg") == "Admin privileges required"


@pytest.mark.asyncio
async def test_admin_app_users_list_merges_entitlements(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        supabase = _make_supabase_admin()

        async def _fetch_list(*, table: str, filters=None, select="*", order=None, limit=20, offset=0, with_count=False):
            if table == "users":
                return (
                    [
                        {
                            "user_id": "user-1",
                            "email": "u1@example.com",
                            "username": "u1",
                            "displayname": "U1",
                            "isanonymous": 0,
                            "isactive": 1,
                            "lastloginat": 0,
                            "createdat": 0,
                            "subscriptionexpirydate": None,
                        },
                        {
                            "user_id": "user-2",
                            "email": "u2@example.com",
                            "username": "u2",
                            "displayname": "U2",
                            "isanonymous": 0,
                            "isactive": 1,
                            "lastloginat": 0,
                            "createdat": 0,
                            "subscriptionexpirydate": None,
                        },
                    ],
                    2 if with_count else None,
                )
            if table == "user_entitlements":
                return (
                    [
                        {
                            "user_id": "user-1",
                            "tier": "pro",
                            "expires_at": 123,
                            "flags": {"skip_prompt": True},
                            "last_updated": 456,
                        }
                    ],
                    None,
                )
            raise AssertionError(f"unexpected table={table}")

        supabase.fetch_list = AsyncMock(side_effect=_fetch_list)

        prev_client = getattr(fastapi_app.state, "supabase_admin", None)
        fastapi_app.state.supabase_admin = supabase
        try:
            resp = await async_client.get(
                "/api/v1/admin/app-users/list",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            payload = resp.json()
            assert payload["code"] == 200
            items = payload["data"]["items"]
            assert len(items) == 2
            by_id = {row["user_id"]: row for row in items}
            assert by_id["user-1"]["tier"] == "pro"
            assert by_id["user-1"]["entitlements_exists"] is True
            assert by_id["user-2"]["tier"] == "free"
            assert by_id["user-2"]["entitlements_exists"] is False
        finally:
            fastapi_app.state.supabase_admin = prev_client


@pytest.mark.asyncio
async def test_admin_app_users_reset_password_disabled_by_default(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        # supabase_auth_admin is required by endpoint, but it should not be called when config forbids reset
        prev_auth = getattr(fastapi_app.state, "supabase_auth_admin", None)
        fastapi_app.state.supabase_auth_admin = MagicMock()
        try:
            resp = await async_client.post(
                "/api/v1/admin/app-users/user-1/reset-password",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"confirm_user_id": "user-1"},
            )
            assert resp.status_code == status.HTTP_200_OK
            payload = resp.json()
            assert payload["code"] == 403
            assert payload["msg"] == "已禁用重置密码（配置）"
        finally:
            fastapi_app.state.supabase_auth_admin = prev_auth


@pytest.mark.asyncio
async def test_admin_app_users_reset_password_enabled_requires_confirm(async_client, mock_jwt_token: str):
    with patch("app.auth.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid="admin-uid",
            claims={"user_metadata": {"username": "admin"}},
            user_type="permanent",
        )
        mock_get_verifier.return_value = mock_verifier

        db = get_sqlite_manager(fastapi_app)
        await db.execute(
            """
            INSERT INTO app_user_admin_settings(key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
            """,
            ("allow_reset_password", json.dumps(True)),
        )

        auth_admin = MagicMock()
        auth_admin.get_user = AsyncMock(return_value={"id": "user-1", "email": "u1@example.com"})
        auth_admin.update_user = AsyncMock(return_value={"id": "user-1"})

        prev_auth = getattr(fastapi_app.state, "supabase_auth_admin", None)
        fastapi_app.state.supabase_auth_admin = auth_admin
        try:
            resp = await async_client.post(
                "/api/v1/admin/app-users/user-1/reset-password",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"confirm_user_id": "not-match"},
            )
            assert resp.status_code == status.HTTP_200_OK
            payload = resp.json()
            assert payload["code"] == 400
            assert payload["msg"] == "二次确认不匹配"
            auth_admin.update_user.assert_not_awaited()
        finally:
            fastapi_app.state.supabase_auth_admin = prev_auth
            await db.execute(
                """
                INSERT INTO app_user_admin_settings(key, value_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
                """,
                ("allow_reset_password", json.dumps(False)),
            )
