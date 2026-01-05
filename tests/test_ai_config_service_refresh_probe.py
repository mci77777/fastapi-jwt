from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.sqlite_manager import SQLiteManager
from app.services.ai_config_service import AIConfigService


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = int(status_code)
        self._payload = payload

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, *args, **kwargs) -> DummyResponse:
        if str(url).endswith("/v1/models"):
            return DummyResponse(200, {"data": [{"id": "m1"}]})
        if str(url).endswith("/v1/chat/completions"):
            # 某些本地代理对 GET 返回 404（只实现 POST），不能据此判定 offline。
            return DummyResponse(404, {"error": "not found"})
        return DummyResponse(404, {"error": "not found"})

    async def options(self, url: str, *args, **kwargs) -> DummyResponse:
        if str(url).endswith("/v1/chat/completions"):
            return DummyResponse(204, None)
        return DummyResponse(404, {"error": "not found"})


def _make_settings() -> SimpleNamespace:
    return SimpleNamespace(http_timeout_seconds=5)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_refresh_endpoint_status_probe_prefers_options(tmp_path, monkeypatch):
    db_path = tmp_path / "db.sqlite"
    storage_dir = tmp_path / "runtime"
    manager = SQLiteManager(db_path)
    await manager.init()
    service = AIConfigService(manager, _make_settings(), storage_dir=storage_dir)
    try:
        endpoint = await service.create_endpoint(
            {
                "name": "local-proxy",
                "base_url": "http://172.19.32.1:8317",
                "api_key": "key123",
            }
        )

        monkeypatch.setattr("app.services.ai_config_service.httpx.AsyncClient", DummyAsyncClient)

        refreshed = await service.refresh_endpoint_status(int(endpoint["id"]))
        assert refreshed["status"] == "online"
        assert refreshed["model_list"] == ["m1"]
    finally:
        await service._db.close()

