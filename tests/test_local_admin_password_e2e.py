from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings


@pytest.mark.asyncio
async def test_local_admin_can_update_password(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    # 让本地 admin token 可被 JWTVerifier 验证（HS256）
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-local-secret")
    monkeypatch.setenv("JWT_AUDIENCE", "authenticated")
    get_settings.cache_clear()
    get_jwt_verifier.cache_clear()

    # 复位：保证 admin 默认密码为 123456（由 /access_token 自动 seed）
    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users WHERE username = ?", ("admin",))

    # 1) 默认登录（admin/123456）
    resp = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "123456"})
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    token = body["data"]["access_token"]

    # 2) 改密码
    resp2 = await async_client.post(
        "/api/v1/base/update_password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "123456", "new_password": "1234567", "confirm_password": "1234567"},
    )
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["code"] == 200

    # 3) 旧密码应失败
    resp3 = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "123456"})
    assert resp3.status_code == status.HTTP_200_OK
    assert resp3.json()["code"] == 401

    # 4) 新密码应成功
    resp4 = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "1234567"})
    assert resp4.status_code == status.HTTP_200_OK
    assert resp4.json()["code"] == 200

    # 清理：避免影响其他用例/本地 db.sqlite3
    await fastapi_app.state.sqlite_manager.execute("DELETE FROM local_users WHERE username = ?", ("admin",))

