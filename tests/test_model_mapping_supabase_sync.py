from __future__ import annotations

from pathlib import Path

import pytest

from app.db import SQLiteManager
from app.services.model_mapping_service import ModelMappingService


class FakeAIConfigServiceWithSupabase:
    def __init__(self, *, remote_snapshot: list[dict] | None = None) -> None:
        self._remote_snapshot = remote_snapshot or []

    async def list_prompts(self, *, page: int, page_size: int, **_: object):
        return [], 0

    async def get_prompt(self, prompt_id: int):  # pragma: no cover
        raise ValueError("prompt_not_found")

    async def update_prompt(self, prompt_id: int, payload: dict):  # pragma: no cover
        return None

    async def fetch_model_mappings_from_supabase(self) -> list[dict]:
        return list(self._remote_snapshot)

    async def write_backup(self, name: str, payload: object, *, keep: int = 3):  # pragma: no cover
        return None


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _new_service(tmp_path: Path, *, remote_snapshot: list[dict] | None = None) -> tuple[ModelMappingService, SQLiteManager]:
    ai_service = FakeAIConfigServiceWithSupabase(remote_snapshot=remote_snapshot)
    db = SQLiteManager(tmp_path / "db.sqlite3")
    await db.init()
    return ModelMappingService(ai_service, db, tmp_path), db


@pytest.mark.anyio("asyncio")
async def test_sync_from_supabase_updates_sqlite(tmp_path: Path) -> None:
    service, db = await _new_service(
        tmp_path,
        remote_snapshot=[
            {
                "id": "mapping:xai",
                "scope_type": "mapping",
                "scope_key": "xai",
                "name": "xAI",
                "default_model": "grok-2",
                "candidates": ["grok-2", "grok-2-mini"],
                "is_active": True,
                "updated_at": "2026-01-18T00:00:00Z",
                "metadata": {"preferred_endpoint_id": 123},
            }
        ],
    )
    try:
        await service.upsert_mapping(
            {
                "scope_type": "mapping",
                "scope_key": "xai",
                "name": "xAI",
                "default_model": "grok-1",
                "candidates": ["grok-1"],
                "is_active": True,
                "metadata": {},
            }
        )
        # 让本地更旧，确保会被远端覆盖
        await db.execute(
            "UPDATE llm_model_mappings SET updated_at = ? WHERE id = ?",
            ["2026-01-17T00:00:00+00:00", "mapping:xai"],
        )

        result = await service.sync_from_supabase(overwrite=False, delete_missing=False)
        assert result["status"] == "pulled"
        assert result["pulled_count"] == 1

        refreshed = await service.list_mappings(scope_type="mapping", scope_key="xai")
        assert refreshed and refreshed[0]["default_model"] == "grok-2"
        assert "grok-2-mini" in refreshed[0]["candidates"]
        assert refreshed[0]["metadata"].get("preferred_endpoint_id") == 123
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_sync_from_supabase_delete_missing(tmp_path: Path) -> None:
    service, db = await _new_service(
        tmp_path,
        remote_snapshot=[
            {
                "id": "mapping:xai",
                "scope_type": "mapping",
                "scope_key": "xai",
                "name": "xAI",
                "default_model": "grok-2",
                "candidates": ["grok-2"],
                "is_active": True,
                "updated_at": "2026-01-18T00:00:00+00:00",
                "metadata": {},
            }
        ],
    )
    try:
        await service.upsert_mapping(
            {
                "scope_type": "mapping",
                "scope_key": "xai",
                "name": "xAI",
                "default_model": "grok-1",
                "candidates": ["grok-1"],
                "is_active": True,
                "metadata": {},
            }
        )
        await service.upsert_mapping(
            {
                "scope_type": "mapping",
                "scope_key": "openai",
                "name": "OpenAI",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini"],
                "is_active": True,
                "metadata": {},
            }
        )

        result = await service.sync_from_supabase(overwrite=True, delete_missing=True)
        assert result["status"] == "pulled"
        assert result["deleted_count"] == 1

        all_mappings = await service.list_mappings()
        ids = {item["id"] for item in all_mappings}
        assert ids == {"mapping:xai"}
    finally:
        await db.close()

