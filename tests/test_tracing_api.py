"""测试请求追踪 API。"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.core.application import create_app
from app.db.sqlite_manager import get_sqlite_manager
from app import app as fastapi_app


@pytest_asyncio.fixture
async def admin_token(async_client: AsyncClient):
    """获取 admin token。"""
    resp = await async_client.post("/api/v1/base/access_token", json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    return body["data"]["access_token"]


@pytest.mark.asyncio
async def test_get_tracing_config(async_client: AsyncClient, admin_token: str):
    """测试获取追踪配置。"""
    response = await async_client.get(
        "/api/v1/tracing/config",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert isinstance(data["enabled"], bool)


@pytest.mark.asyncio
async def test_set_tracing_config(async_client: AsyncClient, admin_token: str):
    """测试设置追踪配置。"""
    response = await async_client.post(
        "/api/v1/tracing/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"enabled": True}
    )
    assert response.status_code == 200

    # 验证设置成功
    response = await async_client.get(
        "/api/v1/tracing/config",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    data = response.json()
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_get_conversation_logs(async_client: AsyncClient, admin_token: str):
    """测试获取对话日志。"""
    response = await async_client.get(
        "/api/v1/tracing/logs",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)
    assert len(data["logs"]) <= 50
