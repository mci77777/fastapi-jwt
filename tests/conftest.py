from __future__ import annotations

import asyncio
import os
from typing import Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

os.environ["SUPABASE_KEEPALIVE_ENABLED"] = "false"
# 硬开关：显式禁用 Supabase Provider（避免读取 .env 与真实网络调用）
os.environ["SUPABASE_PROVIDER_ENABLED"] = "false"
# 测试环境：允许通过 header 验证 LLM 管理端点
os.environ["LLM_ADMIN_API_KEY"] = "test-llm-admin"
# 测试环境强制关闭 Supabase Provider（避免真实网络调用/泄露密钥）
os.environ["SUPABASE_PROJECT_ID"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["AI_MODEL"] = "gpt-4o-mini"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ALLOW_ORIGINS"] = "*"
os.environ["ALLOW_TEST_AI_ENDPOINTS"] = "true"

from app.auth.provider import get_auth_provider
from app.settings.config import get_settings

get_settings.cache_clear()
get_auth_provider.cache_clear()

from app import app as fastapi_app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(fastapi_app) as client:
        yield client


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def mock_jwt_token() -> str:
    return "mock.supabase.jwt"
