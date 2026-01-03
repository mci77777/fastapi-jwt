"""官方动作库（Exercise Library）版本化快照 + diff 计算服务。

对外契约以 `docs/后端方案/动作库-种子数据库scheme-后端须知.md` 为准：
- meta: version/totalCount/lastUpdated/checksum/downloadUrl
- updates: fromVersion/toVersion/added/updated/deleted/timestamp
- full: List<ExerciseDto>
"""

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
    """与 App 侧 ExerciseDto 对齐（camelCase，允许前向字段）。"""

    # 允许携带前向字段，并在发布/快照中保留（避免 admin 发布时丢字段）
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    muscleGroup: str
    category: str
    equipment: list[str]
    difficulty: str
    source: str = "OFFICIAL"
    isCustom: bool = False
    isOfficial: bool = True
    createdAt: int
    updatedAt: int


class ExerciseLibraryMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    totalCount: int
    lastUpdated: int
    checksum: str
    downloadUrl: str | None = None


class ExerciseLibraryUpdates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fromVersion: int
    toVersion: int
    added: list[ExerciseDto]
    updated: list[ExerciseDto]
    deleted: list[str]
    timestamp: int


class ExerciseSeedFile(BaseModel):
    """assets/exercise/exercise_official_seed.json（ExerciseSeedData）。"""

    model_config = ConfigDict(extra="ignore")

    schemaVersion: str | None = None
    entity: str | None = None
    entityVersion: int
    generatedAt: int | None = None
    totalCount: int | None = None
    payload: list[ExerciseDto]


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    version: int
    checksum: str
    generated_at: int | None
    total_count: int
    payload_json: str


@dataclass(frozen=True, slots=True)
class ExerciseLibraryDiff:
    added: list[ExerciseDto]
    updated: list[ExerciseDto]
    deleted: list[str]


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

        payload, seed_meta = self._load_seed_file()
        version_override = None
        generated_at_ms = _now_ms()
        if seed_meta:
            version_override = seed_meta.get("entityVersion")
            generated_at_ms = int(seed_meta.get("generatedAt") or generated_at_ms)
        return await self.publish(payload, generated_at_ms=generated_at_ms, version_override=version_override)

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
        timestamp_ms = int(to_snapshot.generated_at or _now_ms())

        if from_version == to_version:
            return ExerciseLibraryUpdates(
                fromVersion=int(from_version),
                toVersion=int(to_version),
                added=[],
                updated=[],
                deleted=[],
                timestamp=timestamp_ms,
            )

        if from_version == 0:
            return ExerciseLibraryUpdates(
                fromVersion=int(from_version),
                toVersion=int(to_version),
                added=new_items,
                updated=[],
                deleted=[],
                timestamp=timestamp_ms,
            )

        from_snapshot = await self._get_snapshot(from_version)
        old_items = _exercise_list_adapter.validate_python(json.loads(from_snapshot.payload_json))

        diff = self._diff(old_items, new_items)
        return ExerciseLibraryUpdates(
            fromVersion=int(from_version),
            toVersion=int(to_version),
            added=diff.added,
            updated=diff.updated,
            deleted=diff.deleted,
            timestamp=timestamp_ms,
        )

    async def apply_patch_and_publish(
        self,
        *,
        base_version: int,
        added: list[dict[str, Any]] | None = None,
        updated: list[dict[str, Any]] | None = None,
        deleted: list[str] | None = None,
        generated_at_ms: int | None = None,
    ) -> ExerciseLibraryMeta:
        """增量应用 patch（新增/字段级更新/删除）并发布新快照版本。"""

        if base_version < 1:
            raise ExerciseLibraryError("invalid_base_version", "baseVersion must be >= 1")

        # 若尚未有快照，则先从内置 seed 发布 v1
        await self.ensure_seeded()
        latest = await self._get_latest_snapshot()
        if latest is None:
            raise ExerciseLibraryError("exercise_library_not_seeded", "Exercise library is not seeded")

        current_version = int(latest.version)
        if int(base_version) != current_version:
            raise ExerciseLibraryError(
                "version_conflict",
                f"baseVersion={base_version} does not match current version={current_version}",
            )

        try:
            raw_items = json.loads(latest.payload_json)
        except Exception as exc:
            raise ExerciseLibraryError("invalid_snapshot", "Snapshot payload is not valid JSON") from exc

        if not isinstance(raw_items, list):
            raise ExerciseLibraryError("invalid_snapshot", "Snapshot payload must be a JSON array")

        by_id: dict[str, dict[str, Any]] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                continue
            by_id[item_id] = dict(item)

        deleted_ids: list[str] = []
        if deleted:
            for value in deleted:
                item_id = str(value or "").strip()
                if not item_id:
                    continue
                if item_id not in by_id:
                    raise ExerciseLibraryError("patch_target_not_found", f"delete target not found: id={item_id}")
                deleted_ids.append(item_id)
            for item_id in deleted_ids:
                by_id.pop(item_id, None)

        updated_items = updated or []
        ts = int(generated_at_ms if generated_at_ms is not None else _now_ms())
        for patch in updated_items:
            if not isinstance(patch, dict):
                continue
            item_id = str(patch.get("id") or "").strip()
            if not item_id:
                raise ExerciseLibraryError("invalid_patch", "updated item must include non-empty id")
            if item_id not in by_id:
                raise ExerciseLibraryError("patch_target_not_found", f"update target not found: id={item_id}")
            merged = dict(by_id[item_id])
            for key, value in patch.items():
                if key == "id":
                    continue
                merged[key] = value
            # KISS：未显式提供 updatedAt 时，自动刷新为本次发布的时间戳
            if "updatedAt" not in patch:
                merged["updatedAt"] = ts
            by_id[item_id] = merged

        added_items = added or []
        for item in added_items:
            if isinstance(item, ExerciseDto):
                payload = item.model_dump(mode="python")
            elif isinstance(item, dict):
                payload = dict(item)
            else:
                continue
            item_id = str(payload.get("id") or "").strip()
            if not item_id:
                raise ExerciseLibraryError("invalid_patch", "added item must include non-empty id")
            if item_id in by_id:
                raise ExerciseLibraryError("invalid_patch", f"duplicate id in added: {item_id}")
            if "updatedAt" not in payload:
                payload["updatedAt"] = ts
            if "createdAt" not in payload:
                payload["createdAt"] = payload["updatedAt"]
            by_id[item_id] = payload

        # 合并后整体验证（最终对象必须可被 ExerciseDto 接受）
        merged_items: list[ExerciseDto] = []
        for value in by_id.values():
            try:
                merged_items.append(ExerciseDto.model_validate(value))
            except Exception as exc:
                item_id = str(value.get("id") or "").strip()
                raise ExerciseLibraryError("invalid_exercise", f"invalid exercise after patch: id={item_id}") from exc

        return await self.publish(merged_items, generated_at_ms=ts)

    async def publish(
        self,
        items: list[ExerciseDto],
        *,
        generated_at_ms: int | None = None,
        version_override: int | None = None,
    ) -> ExerciseLibraryMeta:
        if not items:
            raise ExerciseLibraryError("empty_seed", "Seed payload must not be empty")

        normalized = [item.model_dump(mode="json") for item in items]
        normalized.sort(key=lambda x: str(x.get("id", "")))
        payload_json = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        checksum = _sha256_hex(_canonical_json(normalized))

        latest = await self._get_latest_snapshot()
        if version_override is None:
            if latest is not None and latest.checksum == checksum:
                return self._row_to_meta(latest)
            next_version = (latest.version + 1) if latest is not None else 1
        else:
            try:
                next_version = int(version_override)
            except Exception as exc:
                raise ExerciseLibraryError("invalid_version", "Version must be an integer") from exc
            if next_version < 1:
                raise ExerciseLibraryError("invalid_version", "Version must be >= 1")
            if latest is not None and next_version <= latest.version:
                raise ExerciseLibraryError(
                    "invalid_version",
                    f"Version must be greater than current version={latest.version}",
                )
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
            totalCount=total_count,
            lastUpdated=generated_at_ms,
            checksum=f"sha256:{checksum}",
            downloadUrl=None,
        )

    def _load_seed_file(self) -> tuple[list[ExerciseDto], dict[str, Any] | None]:
        if not self._seed_path.exists():
            raise ExerciseLibraryError("seed_not_found", f"Seed file not found: {self._seed_path.as_posix()}")
        raw = json.loads(self._seed_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return _exercise_list_adapter.validate_python(raw), None
        if isinstance(raw, dict):
            if "payload" in raw:
                seed = ExerciseSeedFile.model_validate(raw)
                meta = {
                    "entityVersion": seed.entityVersion,
                    "generatedAt": seed.generatedAt,
                    "totalCount": seed.totalCount,
                }
                return seed.payload, meta
            candidate = raw.get("items") or raw.get("exercises")
            if isinstance(candidate, list):
                return _exercise_list_adapter.validate_python(candidate), None
        raise ExerciseLibraryError("invalid_seed_format", "Seed JSON must be a list or an ExerciseSeedData object")

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
        last_updated = int(row.generated_at or 0)
        return ExerciseLibraryMeta(
            version=row.version,
            totalCount=row.total_count,
            lastUpdated=last_updated,
            checksum=f"sha256:{row.checksum}",
            downloadUrl=None,
        )

    def _diff(self, old_items: list[ExerciseDto], new_items: list[ExerciseDto]) -> ExerciseLibraryDiff:
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

        return ExerciseLibraryDiff(added=added, updated=updated, deleted=deleted)
