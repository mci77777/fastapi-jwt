"""官方动作库（Exercise Library）版本化快照 + diff 计算服务。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter

from app.db.sqlite_manager import SQLiteManager


class ExerciseDto(BaseModel):
    """与 App 侧 ExerciseDto 对齐（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    muscleGroup: str
    equipment: str
    description: str | None = None
    imageUrl: str | None = None
    videoUrl: str | None = None
    defaultSets: int
    defaultReps: int
    defaultWeight: float | None = None
    steps: list[str]
    tips: list[str]
    userId: str | None = None
    isCustom: bool
    isFavorite: bool
    difficultyLevel: int
    calories: int | None = None
    targetMuscles: list[str]
    instructions: list[str]
    embedding: str | None = None
    createdAt: int
    updatedAt: int
    createdByUserId: str | None = None


class ExerciseLibraryMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    checksum: str | None = None
    generatedAt: int | None = None
    totalCount: int | None = None


class ExerciseLibraryUpdates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added: list[ExerciseDto]
    updated: list[ExerciseDto]
    deleted: list[str]


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    version: int
    checksum: str
    generated_at: int | None
    total_count: int
    payload_json: str


class ExerciseLibraryError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_exercise_list_adapter: TypeAdapter[list[ExerciseDto]] = TypeAdapter(list[ExerciseDto])


class ExerciseLibraryService:
    """官方动作库快照 SSOT：sqlite.exercise_library_snapshots。"""

    def __init__(self, sqlite_manager: SQLiteManager, *, seed_path: Path) -> None:
        self._db = sqlite_manager
        self._seed_path = Path(seed_path)

    async def ensure_seeded(self) -> ExerciseLibraryMeta:
        """如果尚未发布任何快照，则从内置 seed 发布 v1。"""

        latest = await self._get_latest_snapshot()
        if latest is not None:
            return self._row_to_meta(latest)

        payload = self._load_seed_file()
        return await self.publish(payload, generated_at_ms=_now_ms())

    async def get_meta(self) -> ExerciseLibraryMeta:
        latest = await self._get_latest_snapshot()
        if latest is None:
            raise ExerciseLibraryError("exercise_library_not_seeded", "Exercise library is not seeded")
        return self._row_to_meta(latest)

    async def get_full(self, *, version: int | None = None) -> list[ExerciseDto]:
        snapshot = await self._get_snapshot(version)
        items = _exercise_list_adapter.validate_python(json.loads(snapshot.payload_json))
        return items

    async def get_updates(self, *, from_version: int, to_version: int) -> ExerciseLibraryUpdates:
        if from_version < 0 or to_version < 0:
            raise ExerciseLibraryError("invalid_version", "Version must be >= 0")
        if from_version > to_version:
            raise ExerciseLibraryError("invalid_version_range", "`from` must be <= `to`")

        to_snapshot = await self._get_snapshot(to_version)
        new_items = _exercise_list_adapter.validate_python(json.loads(to_snapshot.payload_json))

        if from_version == to_version:
            return ExerciseLibraryUpdates(added=[], updated=[], deleted=[])

        if from_version == 0:
            return ExerciseLibraryUpdates(added=new_items, updated=[], deleted=[])

        from_snapshot = await self._get_snapshot(from_version)
        old_items = _exercise_list_adapter.validate_python(json.loads(from_snapshot.payload_json))

        return self._diff(old_items, new_items)

    async def publish(self, items: list[ExerciseDto], *, generated_at_ms: int | None = None) -> ExerciseLibraryMeta:
        if not items:
            raise ExerciseLibraryError("empty_seed", "Seed payload must not be empty")

        normalized = [item.model_dump(mode="json") for item in items]
        normalized.sort(key=lambda x: str(x.get("id", "")))
        payload_json = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        checksum = _sha256_hex(_canonical_json(normalized))

        latest = await self._get_latest_snapshot()
        if latest is not None and latest.checksum == checksum:
            return self._row_to_meta(latest)

        next_version = (latest.version + 1) if latest is not None else 1
        total_count = len(normalized)
        generated_at_ms = generated_at_ms if generated_at_ms is not None else _now_ms()

        await self._db.execute(
            """
            INSERT INTO exercise_library_snapshots(version, checksum, generated_at, total_count, payload_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (next_version, checksum, generated_at_ms, total_count, payload_json),
        )

        return ExerciseLibraryMeta(
            version=next_version,
            checksum=checksum,
            generatedAt=generated_at_ms,
            totalCount=total_count,
        )

    def _load_seed_file(self) -> list[ExerciseDto]:
        if not self._seed_path.exists():
            raise ExerciseLibraryError("seed_not_found", f"Seed file not found: {self._seed_path.as_posix()}")
        raw = json.loads(self._seed_path.read_text(encoding="utf-8"))
        return _exercise_list_adapter.validate_python(raw)

    async def _get_latest_snapshot(self) -> SnapshotRow | None:
        row = await self._db.fetchone(
            """
            SELECT version, checksum, generated_at, total_count, payload_json
            FROM exercise_library_snapshots
            ORDER BY version DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        return SnapshotRow(
            version=int(row["version"]),
            checksum=str(row["checksum"]),
            generated_at=(int(row["generated_at"]) if row.get("generated_at") is not None else None),
            total_count=int(row["total_count"]),
            payload_json=str(row["payload_json"]),
        )

    async def _get_snapshot(self, version: int | None) -> SnapshotRow:
        if version is None:
            latest = await self._get_latest_snapshot()
            if latest is None:
                raise ExerciseLibraryError("exercise_library_not_seeded", "Exercise library is not seeded")
            return latest

        row = await self._db.fetchone(
            """
            SELECT version, checksum, generated_at, total_count, payload_json
            FROM exercise_library_snapshots
            WHERE version = ?
            """,
            (int(version),),
        )
        if not row:
            raise ExerciseLibraryError("snapshot_not_found", f"Snapshot not found: version={version}")
        return SnapshotRow(
            version=int(row["version"]),
            checksum=str(row["checksum"]),
            generated_at=(int(row["generated_at"]) if row.get("generated_at") is not None else None),
            total_count=int(row["total_count"]),
            payload_json=str(row["payload_json"]),
        )

    def _row_to_meta(self, row: SnapshotRow) -> ExerciseLibraryMeta:
        return ExerciseLibraryMeta(
            version=row.version,
            checksum=row.checksum,
            generatedAt=row.generated_at,
            totalCount=row.total_count,
        )

    def _diff(self, old_items: list[ExerciseDto], new_items: list[ExerciseDto]) -> ExerciseLibraryUpdates:
        old_by_id = {item.id: item for item in old_items}
        new_by_id = {item.id: item for item in new_items}

        old_ids = set(old_by_id.keys())
        new_ids = set(new_by_id.keys())

        added_ids = sorted(new_ids - old_ids)
        deleted_ids = sorted(old_ids - new_ids)
        common_ids = sorted(old_ids & new_ids)

        added = [new_by_id[item_id] for item_id in added_ids]
        deleted = deleted_ids

        updated: list[ExerciseDto] = []
        for item_id in common_ids:
            old_payload = old_by_id[item_id].model_dump(mode="json")
            new_payload = new_by_id[item_id].model_dump(mode="json")
            if _sha256_hex(_canonical_json(old_payload)) != _sha256_hex(_canonical_json(new_payload)):
                updated.append(new_by_id[item_id])

        return ExerciseLibraryUpdates(added=added, updated=updated, deleted=deleted)

