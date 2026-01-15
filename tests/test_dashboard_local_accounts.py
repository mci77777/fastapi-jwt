from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings


@pytest.mark.asyncio
async def test_dashboard_local_accounts_rbac(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-local-secret")
    monkeypatch.setenv("JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("SUPABASE_ISSUER", "https://example.supabase.co/")
    get_settings.cache_clear()
    get_jwt_verifier.cache_clear()

    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users", ())

    # 1) admin 默认登录（会自动 seed admin/123456）
    resp = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "123456"})
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    admin_token = body["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2) 创建次级账号（user）
    created = await async_client.post(
        "/api/v1/admin/dashboard-users/create",
        headers=admin_headers,
        json={"username": "ops1", "password": "ops1pass", "role": "user", "is_active": True},
    )
    assert created.status_code == status.HTTP_200_OK
    assert created.json()["code"] == 200

    # 3) 次级账号登录与菜单裁剪
    resp2 = await async_client.post("/api/v1/base/access_token", json={"username": "ops1", "password": "ops1pass"})
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["code"] == 200
    ops_token = resp2.json()["data"]["access_token"]
    ops_headers = {"Authorization": f"Bearer {ops_token}"}

    menu = await async_client.get("/api/v1/base/usermenu", headers=ops_headers)
    assert menu.status_code == status.HTTP_200_OK
    menus = menu.json()["data"]
    assert isinstance(menus, list)
    assert any(m.get("name") == "Dashboard" for m in menus)
    assert not any(m.get("name") == "系统管理" for m in menus)

    denied = await async_client.get("/api/v1/admin/app-users/bootstrap", headers=ops_headers)
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    # 4) 提升为 manager 后允许写入 LLM 配置
    updated = await async_client.post(
        "/api/v1/admin/dashboard-users/ops1/role",
        headers=admin_headers,
        json={"role": "manager", "confirm_username": "ops1"},
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["code"] == 200

    menu2 = await async_client.get("/api/v1/base/usermenu", headers=ops_headers)
    assert menu2.status_code == status.HTTP_200_OK
    menus2 = menu2.json()["data"]
    assert any(m.get("name") == "系统管理" for m in menus2)
    assert any(m.get("name") == "AI模型管理" for m in menus2)

    payload = {"name": "endpoint-guard-llm-admin", "base_url": "https://api.openai.com"}
    llm_write = await async_client.post("/api/v1/llm/models", headers=ops_headers, json=payload)
    assert llm_write.status_code == status.HTTP_200_OK

    # 5) 禁用账号后禁止登录
    disabled = await async_client.post(
        "/api/v1/admin/dashboard-users/ops1/disable",
        headers=admin_headers,
        json={"confirm_username": "ops1"},
    )
    assert disabled.status_code == status.HTTP_200_OK
    assert disabled.json()["code"] == 200

    denied_login = await async_client.post("/api/v1/base/access_token", json={"username": "ops1", "password": "ops1pass"})
    assert denied_login.status_code == status.HTTP_200_OK
    assert denied_login.json()["code"] == 403

    # 6) 重置密码（允许在禁用状态下执行），再启用后用新密码登录
    reset = await async_client.post(
        "/api/v1/admin/dashboard-users/ops1/reset-password",
        headers=admin_headers,
        json={"confirm_username": "ops1", "password_length": 12},
    )
    assert reset.status_code == status.HTTP_200_OK
    reset_body = reset.json()
    assert reset_body["code"] == 200
    new_password = reset_body["data"]["password"]

    enabled = await async_client.post(
        "/api/v1/admin/dashboard-users/ops1/enable",
        headers=admin_headers,
        json={"confirm_username": "ops1"},
    )
    assert enabled.status_code == status.HTTP_200_OK
    assert enabled.json()["code"] == 200

    old_pwd_failed = await async_client.post("/api/v1/base/access_token", json={"username": "ops1", "password": "ops1pass"})
    assert old_pwd_failed.status_code == status.HTTP_200_OK
    assert old_pwd_failed.json()["code"] == 401

    new_pwd_ok = await async_client.post("/api/v1/base/access_token", json={"username": "ops1", "password": new_password})
    assert new_pwd_ok.status_code == status.HTTP_200_OK
    assert new_pwd_ok.json()["code"] == 200

    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users", ())


@pytest.mark.asyncio
async def test_cannot_remove_last_active_super_admin(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-local-secret")
    monkeypatch.setenv("JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("SUPABASE_ISSUER", "https://example.supabase.co/")
    get_settings.cache_clear()
    get_jwt_verifier.cache_clear()

    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users", ())

    resp = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "123456"})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    downgrade = await async_client.post(
        "/api/v1/admin/dashboard-users/admin/role",
        headers=headers,
        json={"role": "user", "confirm_username": "admin"},
    )
    assert downgrade.status_code == status.HTTP_200_OK
    assert downgrade.json()["code"] == 400

    disable = await async_client.post(
        "/api/v1/admin/dashboard-users/admin/disable",
        headers=headers,
        json={"confirm_username": "admin"},
    )
    assert disable.status_code == status.HTTP_200_OK
    assert disable.json()["code"] == 400

    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users", ())
