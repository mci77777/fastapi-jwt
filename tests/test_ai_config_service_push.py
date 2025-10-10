from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.sqlite_manager import SQLiteManager
from app.services.ai_config_service import AIConfigService


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - no error path in tests
        return None

    def json(self):
        return self._payload


class DummyHttpClient:
    def __init__(self, response_payload):
        self._payload = response_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return DummyResponse(self._payload)

    async def patch(self, *args, **kwargs):
        return DummyResponse(self._payload)


def _make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        http_timeout_seconds=5,
        supabase_service_role_key="test-role",
        supabase_project_id="project-id",
    )


async def _make_service(tmp_path) -> AIConfigService:
    db_path = tmp_path / "db.sqlite"
    storage_dir = tmp_path / "runtime"
    manager = SQLiteManager(db_path)
    await manager.init()
    settings = _make_settings()
    service = AIConfigService(manager, settings, storage_dir=storage_dir)
    return service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_write_backup_rotates_and_keeps_latest(tmp_path):
    service = await _make_service(tmp_path)
    try:
        for i in range(5):
            await service._write_backup("supabase_endpoints", [{"id": i}], keep=3)

        backups_dir = service._backup_dir
        latest = backups_dir / "supabase_endpoints-latest.json"
        assert latest.exists()

        archives = sorted(
            path
            for path in backups_dir.glob("supabase_endpoints-*.json")
            if path.name != "supabase_endpoints-latest.json"
        )

        assert len(archives) == 3
    finally:
        await service._db.close()


@pytest.mark.anyio("asyncio")
async def test_push_endpoint_skips_when_remote_is_newer(tmp_path, monkeypatch):
    service = await _make_service(tmp_path)
    try:
        endpoint = await service.create_endpoint(
            {
                "name": "test-endpoint",
                "base_url": "https://api.example.com",
                "model": "gpt-4",
            }
        )

        await service._db.execute(
            "UPDATE ai_endpoints SET supabase_id = ?, updated_at = ? WHERE id = ?",
            [123, "2025-01-01T00:00:00+00:00", endpoint["id"]],
        )

        called_ids: list[int] = []

        async def fake_fetch(self, supabase_id: int):
            called_ids.append(supabase_id)
            return {"id": supabase_id, "updated_at": "2025-02-01T00:00:00+00:00"}

        monkeypatch.setattr(AIConfigService, "_fetch_supabase_model", fake_fetch, raising=True)

        result = await service.push_endpoint_to_supabase(endpoint["id"], overwrite=False)

        assert result["sync_status"] == "skipped:overwrite_disabled"
        assert result["last_synced_at"] is not None
        assert called_ids == [123]
    finally:
        await service._db.close()


@pytest.mark.anyio("asyncio")
async def test_push_endpoint_deletes_remote_when_requested(tmp_path, monkeypatch):
    service = await _make_service(tmp_path)
    try:
        endpoint = await service.create_endpoint(
            {
                "name": "new-endpoint",
                "base_url": "https://api.example.com",
                "model": "gpt-4-mini",
            }
        )

        remote_snapshot = [
            {"id": 321, "updated_at": "2025-01-01T00:00:00+00:00"},
            {"id": 999, "updated_at": "2025-01-01T00:00:00+00:00"},
        ]

        async def fake_fetch_models(self):
            return list(remote_snapshot)

        async def fake_fetch_model(self, supabase_id: int):
            for item in remote_snapshot:
                if int(item["id"]) == int(supabase_id):
                    return item
            return None

        deleted: list[int] = []

        async def fake_delete(self, supabase_id: int):
            deleted.append(supabase_id)

        monkeypatch.setattr(AIConfigService, "_fetch_supabase_models", fake_fetch_models, raising=True)
        monkeypatch.setattr(AIConfigService, "_fetch_supabase_model", fake_fetch_model, raising=True)
        monkeypatch.setattr(AIConfigService, "_delete_supabase_endpoint", fake_delete, raising=True)

        payload = [{"id": 321, "updated_at": "2025-01-01T00:00:00+00:00"}]

        def fake_client(*args, **kwargs):
            return DummyHttpClient(payload)

        monkeypatch.setattr("app.services.ai_config_service.httpx.AsyncClient", fake_client)

        result = await service.push_endpoint_to_supabase(endpoint["id"], delete_missing=True)

        assert result["supabase_id"] == 321
        assert deleted == [999]
    finally:
        await service._db.close()
