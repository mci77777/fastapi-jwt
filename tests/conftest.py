from __future__ import annotations

import asyncio
import os
import shutil
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# 测试隔离：避免污染本地持久化 data/db.sqlite3（会导致“测试端点”越跑越多）
os.environ["SQLITE_DB_PATH"] = "tmp_test/pytest_db.sqlite3"

os.environ["SUPABASE_KEEPALIVE_ENABLED"] = "false"
# 硬开关：显式禁用 Supabase Provider（避免读取 .env 与真实网络调用）
os.environ["SUPABASE_PROVIDER_ENABLED"] = "false"
# 测试环境：禁用启动期端点探针（避免真实外网调用与用例间串扰）
os.environ["ENDPOINT_MONITOR_PROBE_ENABLED"] = "false"
# 测试环境强制关闭 Supabase Provider（避免真实网络调用/泄露密钥）
os.environ["SUPABASE_PROJECT_ID"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
# 确保测试环境存在“最小可用默认端点”，让 model 白名单（/api/v1/llm/models）非空
os.environ["AI_PROVIDER"] = "openai"
os.environ["AI_API_KEY"] = "test-ai-key"
os.environ["AI_MODEL"] = "gpt-4o-mini"
os.environ["AI_RUNTIME_STORAGE_DIR"] = "tmp_test/ai_runtime"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ALLOW_ORIGINS"] = "*"
os.environ["ALLOW_TEST_AI_ENDPOINTS"] = "true"

try:
    os.makedirs("tmp_test", exist_ok=True)
    # 测试隔离：避免污染仓库内 storage/ai_runtime（会导致映射/屏蔽列表跨用例漂移）
    shutil.rmtree(os.environ["AI_RUNTIME_STORAGE_DIR"], ignore_errors=True)
    os.makedirs(os.environ["AI_RUNTIME_STORAGE_DIR"], exist_ok=True)
    if os.path.exists(os.environ["SQLITE_DB_PATH"]):
        os.remove(os.environ["SQLITE_DB_PATH"])
except Exception:
    # 测试环境兜底：不因清理失败阻断 import
    pass

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


@pytest.fixture(autouse=True)
def _mock_ai_service_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认禁用 AIService 的真实外网调用（允许用例自行 patch 覆盖）。"""

    from app.services import ai_service as ai_service_module

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "test response"}}],
    }
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_stream_response = MagicMock()
    mock_stream_response.status_code = 200
    mock_stream_response.headers = {"content-type": "application/json"}
    mock_stream_response.raise_for_status = MagicMock()
    mock_stream_response.aread = AsyncMock(
        return_value=b'{"choices":[{"message":{"content":"test response"}}]}',
    )

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_ctx = MagicMock()
    mock_client = mock_ctx.__aenter__.return_value
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_ctx.__aexit__.return_value = False

    monkeypatch.setattr(ai_service_module.httpx, "AsyncClient", MagicMock(return_value=mock_ctx))
