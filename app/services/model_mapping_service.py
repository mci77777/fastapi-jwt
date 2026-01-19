"""模型映射管理服务。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db import SQLiteManager
from app.services.ai_config_service import AIConfigService
from app.services.ai_model_rules import looks_like_embedding_model

MAPPING_KEY = "__model_mapping"
BLOCKED_MODELS_KEY = "__blocked_models"

_SCOPE_TYPE_ALIASES: dict[str, str] = {
    # 历史：tenant 被用于“映射名”业务域；为消歧更名为 mapping。
    "tenant": "mapping",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping_id(scope_type: str, scope_key: str) -> str:
    return f"{scope_type}:{scope_key}"


def _normalize_scope_type(scope_type: str | None) -> str:
    value = str(scope_type or "").strip()
    return _SCOPE_TYPE_ALIASES.get(value, value)


def _normalize_mapping_id(mapping_id: str) -> str:
    text = str(mapping_id or "").strip()
    if not text or ":" not in text:
        return text
    scope_type, scope_key = text.split(":", 1)
    scope_type = _normalize_scope_type(scope_type)
    return _mapping_id(scope_type, scope_key)


def normalize_scope_type(scope_type: str | None) -> str:
    """对外暴露的 scope_type 归一化（SSOT：tenant -> mapping）。"""

    return _normalize_scope_type(scope_type)


def normalize_mapping_id(mapping_id: str) -> str:
    """对外暴露的 mapping_id 归一化（SSOT：tenant:* -> mapping:*）。"""

    return _normalize_mapping_id(mapping_id)


@dataclass(slots=True)
class ModelMapping:
    id: str
    scope_type: str
    scope_key: str
    name: str | None
    default_model: str | None
    candidates: list[str]
    is_active: bool
    updated_at: str | None
    source: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scope_type": self.scope_type,
            "scope_key": self.scope_key,
            "name": self.name,
            "default_model": self.default_model,
            "candidates": self.candidates,
            "is_active": self.is_active,
            "updated_at": self.updated_at,
            "source": self.source,
            "metadata": self.metadata,
        }


class ModelMappingService:
    """负责读取/写入 Prompt + SQLite 中的模型映射配置（SSOT）。

    兼容：启动期会把 legacy JSON（AI_RUNTIME_STORAGE_DIR/model_mappings.json）一次性导入 SQLite。
    """

    def __init__(
        self,
        ai_service: AIConfigService,
        db: SQLiteManager,
        storage_dir: Path,
        *,
        auto_seed_enabled: bool = False,
    ) -> None:
        self._ai_service = ai_service
        self._db = db
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._legacy_file_path = self._storage_dir / "model_mappings.json"
        self._blocked_file_path = self._storage_dir / "blocked_models.json"
        self._sqlite_import_marker = self._storage_dir / ".model_mappings_sqlite_import_done"
        self._lock = asyncio.Lock()
        self._auto_seed_enabled = bool(auto_seed_enabled)
        self._sqlite_import_done = False

    async def list_blocked_models(self) -> list[str]:
        payload = await self._read_blocked()
        blocked = payload.get("blocked") if isinstance(payload, dict) else None
        if not isinstance(blocked, list):
            return []
        items: list[str] = []
        for value in blocked:
            text = str(value or "").strip()
            if text:
                items.append(text)
        return sorted(set(items))

    async def upsert_blocked_models(self, updates: list[dict[str, Any]]) -> list[str]:
        normalized: list[tuple[str, bool]] = []
        for item in updates:
            if not isinstance(item, dict):
                continue
            model = str(item.get("model") or "").strip()
            if not model:
                continue
            blocked = bool(item.get("blocked", True))
            normalized.append((model, blocked))

        async with self._lock:
            payload = await self._read_blocked_unlocked()
            existing = payload.get("blocked") if isinstance(payload, dict) else None
            blocked_set: set[str] = set()
            if isinstance(existing, list):
                for value in existing:
                    text = str(value or "").strip()
                    if text:
                        blocked_set.add(text)

            for model, blocked in normalized:
                if blocked:
                    blocked_set.add(model)
                else:
                    blocked_set.discard(model)

            new_payload = {
                "updated_at": _utc_now(),
                "blocked": sorted(blocked_set),
            }
            await asyncio.to_thread(
                self._blocked_file_path.write_text,
                json.dumps(new_payload, ensure_ascii=False, indent=2),
                "utf-8",
            )
            return list(new_payload["blocked"])

    async def list_mappings(
        self,
        *,
        scope_type: str | None = None,
        scope_key: str | None = None,
    ) -> list[dict[str, Any]]:
        await self._ensure_sqlite_imported()
        normalized_scope_type = _normalize_scope_type(scope_type) if scope_type else None
        prompt_mappings = (
            await self._collect_prompt_mappings()
            if (normalized_scope_type is None or normalized_scope_type == "prompt")
            else []
        )
        sqlite_mappings = await self._collect_sqlite_mappings(scope_type=normalized_scope_type, scope_key=scope_key)
        combined: list[ModelMapping] = prompt_mappings + sqlite_mappings
        if normalized_scope_type:
            combined = [item for item in combined if item.scope_type == normalized_scope_type]
        if scope_key:
            combined = [item for item in combined if item.scope_key == scope_key]
        return [item.to_dict() for item in combined]

    async def upsert_mapping(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_sqlite_imported()
        scope_type = _normalize_scope_type(payload["scope_type"])
        scope_key = str(payload["scope_key"])
        candidates = list(dict.fromkeys(payload.get("candidates") or []))
        default_model = payload.get("default_model")
        if default_model and default_model not in candidates:
            candidates.append(default_model)
        mapping = {
            "candidates": candidates,
            "default_model": default_model,
            "is_active": bool(payload.get("is_active", True)),
            "updated_at": _utc_now(),
            "metadata": payload.get("metadata") or {},
        }

        if scope_type == "prompt":
            await self._write_prompt_mapping(int(scope_key), mapping)
        else:
            await self._upsert_sqlite_mapping(scope_type, scope_key, payload.get("name"), mapping)
        results = await self.list_mappings(scope_type=scope_type, scope_key=scope_key)
        return results[0] if results else {}

    async def ensure_minimal_global_mapping(self) -> dict[str, Any] | None:
        """当系统没有任何可用映射时，按当前端点配置生成一个最小 global 映射，保证 App 可选模型非空。"""

        existing = await self.list_mappings(scope_type="global", scope_key="global")
        if existing:
            return existing[0]

        if not self._auto_seed_enabled:
            return None

        endpoints, _ = await self._ai_service.list_endpoints(only_active=True, page=1, page_size=200)
        active = [ep for ep in endpoints if isinstance(ep, dict) and ep.get("is_active") and ep.get("has_api_key")]
        if not active:
            return None

        default_endpoint = next((ep for ep in active if ep.get("is_default")), active[0])
        blocked = set(await self.list_blocked_models())

        candidates: list[str] = []
        preferred = default_endpoint.get("model")
        if (
            isinstance(preferred, str)
            and preferred.strip()
            and preferred.strip() not in blocked
            and not looks_like_embedding_model(preferred.strip())
        ):
            candidates.append(preferred.strip())

        model_list = default_endpoint.get("model_list") or []
        if isinstance(model_list, list):
            for value in model_list:
                text = str(value or "").strip()
                if (
                    text
                    and text not in blocked
                    and text not in candidates
                    and not looks_like_embedding_model(text)
                ):
                    candidates.append(text)

        # 兜底：从其他端点补齐少量候选，确保首屏至少可选 1 个
        if not candidates:
            for ep in active:
                text = str(ep.get("model") or "").strip()
                if (
                    text
                    and text not in blocked
                    and text not in candidates
                    and not looks_like_embedding_model(text)
                ):
                    candidates.append(text)
                if len(candidates) >= 10:
                    break

        if not candidates:
            return None

        return await self.upsert_mapping(
            {
                "scope_type": "global",
                "scope_key": "global",
                "name": "App Default",
                "default_model": candidates[0],
                "candidates": candidates,
                "is_active": True,
                "metadata": {"source": "auto_seed"},
            }
        )

    async def ensure_test_claude_opus_mapping(self) -> dict[str, Any] | None:
        """测试期默认映射：claude-opus（高级模型）。

        仅在 allow_test_ai_endpoints=true 时启用，避免生产环境出现“删不掉/回弹”的隐式配置。
        """

        if not self._auto_seed_enabled:
            return None

        existing = await self.list_mappings(scope_type="mapping", scope_key="claude-opus")
        if existing:
            return existing[0]

        return await self.upsert_mapping(
            {
                "scope_type": "mapping",
                "scope_key": "claude-opus",
                "name": "claude-opus",
                "default_model": "claude-opus-4-5-20251101",
                "candidates": ["claude-opus-4-5-20251101"],
                "is_active": True,
                "metadata": {"required_tier": "pro"},
            }
        )

    async def activate_default(self, mapping_id: str, default_model: str) -> dict[str, Any]:
        await self._ensure_sqlite_imported()
        scope_type, scope_key = self._split_mapping_id(mapping_id)
        scope_type = _normalize_scope_type(scope_type)
        results = await self.list_mappings(scope_type=scope_type, scope_key=scope_key)
        if not results:
            raise ValueError("mapping_not_found")
        mapping = results[0]
        payload = {
            "scope_type": scope_type,
            "scope_key": scope_key,
            "name": mapping.get("name"),
            "candidates": list(mapping.get("candidates") or []),
            "default_model": default_model,
            "is_active": True,
            "metadata": mapping.get("metadata") or {},
        }
        return await self.upsert_mapping(payload)

    async def delete_mapping(self, mapping_id: str) -> bool:
        """删除一条映射（prompt 映射写回 ai_prompts.tools_json；其他映射写回 SQLite）。"""

        await self._ensure_sqlite_imported()
        scope_type, scope_key = self._split_mapping_id(mapping_id)
        scope_type = _normalize_scope_type(scope_type)

        if scope_type == "prompt":
            try:
                prompt_id = int(scope_key)
            except Exception as exc:
                raise ValueError("invalid_mapping_id") from exc

            prompt = await self._ai_service.get_prompt(prompt_id)
            tools = prompt.get("tools_json")

            container: dict[str, Any]
            if isinstance(tools, dict):
                container = dict(tools)
            elif isinstance(tools, list):
                container = {"tools": tools}
            elif tools is None:
                container = {}
            else:
                container = {"raw": tools}

            if MAPPING_KEY not in container:
                return False
            container.pop(MAPPING_KEY, None)
            await self._ai_service.update_prompt(prompt_id, {"tools_json": container})
            return True

        return await self._delete_sqlite_mapping(scope_type, scope_key)

    async def resolve_model_key(self, model_key: str) -> dict[str, Any]:
        """将“映射模型 key”解析为可用于上游调用的真实模型名（并强制跳过被屏蔽模型）。"""

        key = str(model_key or "").strip()
        if not key:
            return {"resolved_model": None, "hit": False}

        try:
            mappings = await self.list_mappings()
        except Exception:
            return {"resolved_model": key, "hit": False}

        mapping: dict[str, Any] | None = None
        normalized_key = _normalize_mapping_id(key) if ":" in key else key
        if ":" in normalized_key:
            mapping = next((m for m in mappings if m.get("id") == normalized_key and m.get("is_active", True)), None)
        else:
            # 兼容 App 业务 key（无 scope_type 前缀）：优先 mapping，其次 global
            scope_priority = ("mapping", "global")
            best: dict[str, Any] | None = None
            best_pri = 999
            best_updated = ""
            for item in mappings:
                if not isinstance(item, dict) or not item.get("is_active", True):
                    continue
                if str(item.get("scope_key") or "").strip() != key:
                    continue
                scope_type = _normalize_scope_type(item.get("scope_type"))
                if scope_type not in scope_priority:
                    continue
                pri = scope_priority.index(scope_type)
                updated = str(item.get("updated_at") or "")
                if best is None or pri < best_pri or (pri == best_pri and updated > best_updated):
                    best = item
                    best_pri = pri
                    best_updated = updated
            mapping = best
        if not isinstance(mapping, dict):
            return {"resolved_model": key, "hit": False}

        meta = mapping.get("metadata") if isinstance(mapping.get("metadata"), dict) else {}

        preferred_endpoint_id: int | None = None
        if isinstance(meta, dict):
            for field in ("preferred_endpoint_id", "endpoint_id", "endpointId"):
                raw = meta.get(field)
                if raw is None or isinstance(raw, bool):
                    continue
                try:
                    preferred_endpoint_id = int(raw)
                    break
                except (TypeError, ValueError):
                    continue

        blocked = set(await self.list_blocked_models())

        ordered: list[str] = []
        default_model = mapping.get("default_model")
        if isinstance(default_model, str) and default_model.strip():
            ordered.append(default_model.strip())
        candidates = mapping.get("candidates") or []
        if isinstance(candidates, list):
            for value in candidates:
                text = str(value or "").strip()
                if text:
                    ordered.append(text)

        for candidate in ordered:
            if candidate in blocked:
                continue
            return {
                "resolved_model": candidate,
                "hit": True,
                "mapping_id": mapping.get("id"),
                "scope_type": mapping.get("scope_type"),
                "scope_key": mapping.get("scope_key"),
                "metadata": meta,
                "preferred_endpoint_id": preferred_endpoint_id,
            }

        # 命中映射但无可用模型：交给调用方做 fallback（避免把被屏蔽 key 直接打到上游）
        return {
            "resolved_model": None,
            "hit": True,
            "mapping_id": mapping.get("id"),
            "scope_type": mapping.get("scope_type"),
            "scope_key": mapping.get("scope_key"),
            "metadata": meta,
            "preferred_endpoint_id": preferred_endpoint_id,
        }

    async def sync_to_supabase(self, *, delete_missing: bool = False) -> dict[str, Any]:
        """把当前映射推送到 Supabase（若未配置 Supabase，则返回 skipped）。"""

        mappings = await self.list_mappings()
        return await self._ai_service.push_model_mappings_to_supabase(mappings, delete_missing=delete_missing)

    async def sync_from_supabase(
        self,
        *,
        overwrite: bool = False,
        delete_missing: bool = False,
    ) -> dict[str, Any]:
        """从 Supabase 拉取映射并写入 SQLite（仅 scope_type != prompt 的映射）。"""

        await self._ensure_sqlite_imported()

        try:
            remote_snapshot = await self._ai_service.fetch_model_mappings_from_supabase()
        except RuntimeError as exc:
            if str(exc) == "supabase_not_configured":
                return {
                    "status": "skipped:supabase_not_configured",
                    "pulled_count": 0,
                    "skipped_count": 0,
                    "deleted_count": 0,
                }
            raise

        # 备份：便于回滚（与 push 使用同一备份名，始终保持 latest 可用）
        try:
            local_snapshot = [item.to_dict() for item in await self._collect_sqlite_mappings()]
            await self._ai_service.write_backup("sqlite_model_mappings", local_snapshot)
            await self._ai_service.write_backup("supabase_model_mappings", remote_snapshot)
        except Exception:  # pragma: no cover - 备份失败不阻断拉取
            pass

        def _parse_ts(value: Any) -> datetime | None:
            if not isinstance(value, str) or not value.strip():
                return None
            text = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return None

        def _normalize_ts(value: Any) -> str | None:
            if not isinstance(value, str) or not value.strip():
                return None
            return value.strip().replace("Z", "+00:00")

        pulled_count = 0
        skipped_count = 0
        seen_ids: set[str] = set()

        for item in remote_snapshot:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                continue

            normalized_id = _normalize_mapping_id(raw_id.strip())
            if ":" not in normalized_id:
                continue
            scope_type, scope_key = normalized_id.split(":", 1)
            scope_type = _normalize_scope_type(scope_type)
            scope_key = str(scope_key or "").strip()
            if not scope_type or not scope_key:
                continue
            if scope_type == "prompt":
                continue

            mapping_id = _mapping_id(scope_type, scope_key)
            seen_ids.add(mapping_id)

            local_row = await self._db.fetchone("SELECT updated_at FROM llm_model_mappings WHERE id = ?", (mapping_id,))
            local_ts = _parse_ts(local_row.get("updated_at") if local_row else None)
            remote_ts = _parse_ts(item.get("updated_at"))
            if not overwrite and local_ts and remote_ts and local_ts >= remote_ts:
                skipped_count += 1
                continue

            candidates: list[str] = []
            raw_candidates = item.get("candidates")
            if isinstance(raw_candidates, list):
                for value in raw_candidates:
                    text = str(value or "").strip()
                    if text:
                        candidates.append(text)
            candidates = list(dict.fromkeys(candidates))

            default_text: str | None = None
            raw_default = item.get("default_model")
            if isinstance(raw_default, str) and raw_default.strip():
                default_text = raw_default.strip()
            if default_text and default_text not in candidates:
                candidates.append(default_text)

            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            mapping = {
                "default_model": default_text,
                "candidates": candidates,
                "is_active": bool(item.get("is_active", True)),
                "updated_at": _normalize_ts(item.get("updated_at")) or _utc_now(),
                "metadata": metadata,
            }
            name = item.get("name") if isinstance(item.get("name"), str) else None
            await self._upsert_sqlite_mapping(scope_type, scope_key, name, mapping)
            pulled_count += 1

        deleted_count = 0
        if delete_missing:
            before_row = await self._db.fetchone("SELECT COUNT(1) AS cnt FROM llm_model_mappings")
            before_count = int(before_row.get("cnt") or 0) if before_row else 0
            if seen_ids:
                placeholders = ",".join(["?"] * len(seen_ids))
                await self._db.execute(
                    f"DELETE FROM llm_model_mappings WHERE id NOT IN ({placeholders})",
                    list(seen_ids),
                )
            else:
                await self._db.execute("DELETE FROM llm_model_mappings")
            after_row = await self._db.fetchone("SELECT COUNT(1) AS cnt FROM llm_model_mappings")
            after_count = int(after_row.get("cnt") or 0) if after_row else 0
            deleted_count = max(0, before_count - after_count)

        return {
            "status": "pulled",
            "pulled_count": pulled_count,
            "skipped_count": skipped_count,
            "deleted_count": deleted_count,
            "remote_total": len(remote_snapshot),
        }

    async def import_local_mappings(self, mappings: list[dict[str, Any]]) -> dict[str, Any]:
        """从本地 JSON 快照导入映射（仅 upsert，不删除）。"""

        await self._ensure_sqlite_imported()
        imported_count = 0
        skipped_count = 0
        errors: list[dict[str, Any]] = []

        for index, item in enumerate(mappings):
            if not isinstance(item, dict):
                skipped_count += 1
                errors.append({"index": index, "reason": "invalid_item"})
                continue

            scope_type = item.get("scope_type")
            scope_key = item.get("scope_key")
            raw_id = item.get("id")
            if (not scope_type or not scope_key) and isinstance(raw_id, str) and ":" in raw_id:
                parsed_scope_type, parsed_scope_key = raw_id.split(":", 1)
                scope_type = scope_type or parsed_scope_type
                scope_key = scope_key or parsed_scope_key

            scope_type = _normalize_scope_type(scope_type)
            scope_key = str(scope_key or "").strip()
            if not scope_type or not scope_key:
                skipped_count += 1
                errors.append({"index": index, "id": raw_id, "reason": "missing_scope"})
                continue

            name = item.get("name") if isinstance(item.get("name"), str) else None

            default_model = item.get("default_model")
            if isinstance(default_model, str):
                default_model = default_model.strip() or None
            else:
                default_model = None

            candidates: list[str] = []
            raw_candidates = item.get("candidates")
            if isinstance(raw_candidates, list):
                for value in raw_candidates:
                    text = str(value or "").strip()
                    if text:
                        candidates.append(text)
            candidates = list(dict.fromkeys(candidates))

            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            payload = {
                "scope_type": scope_type,
                "scope_key": scope_key,
                "name": name,
                "default_model": default_model,
                "candidates": candidates,
                "is_active": bool(item.get("is_active", True)),
                "metadata": metadata,
            }

            try:
                await self.upsert_mapping(payload)
            except Exception as exc:  # pragma: no cover - 单条失败不应阻断批量导入
                skipped_count += 1
                errors.append({"index": index, "id": raw_id, "reason": str(exc)})
                continue

            imported_count += 1

        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    async def resolve_for_message(
        self,
        *,
        user_id: str,
        tenant_id: str | None = None,
        prompt_id: int | None = None,
    ) -> dict[str, Any]:
        """为一次 messages 请求解析模型选择（SSOT：prompt tools_json + SQLite）。

        优先级（越靠前越优先）：prompt → user → mapping → global。

        Returns:
            dict: {
              "model": str|None,
              "temperature": float|None,
              "hit": {"scope_type":..., "scope_key":..., "source":...}|None,
              "chain": [{"scope_type":..., "scope_key":..., "source":..., "found":bool, "active":bool}...],
              "reason": str|None
            }
        """

        chain: list[dict[str, Any]] = []

        prompt_mapping = await self._read_prompt_mapping(prompt_id) if prompt_id else None
        await self._ensure_sqlite_imported()

        candidates: list[tuple[str, str | None, str]] = []
        if prompt_id is not None:
            candidates.append(("prompt", str(prompt_id), "prompt"))
        candidates.append(("user", user_id, "fallback"))
        if tenant_id:
            candidates.append(("mapping", str(tenant_id), "fallback"))
        candidates.append(("global", "global", "fallback"))

        blocked_models = set(await self.list_blocked_models())

        def _pick(mapping: dict[str, Any]) -> tuple[str | None, float | None, str | None]:
            default_model = mapping.get("default_model")
            candidates_list = mapping.get("candidates") or []

            ordered: list[tuple[str, str]] = []
            if isinstance(default_model, str) and default_model.strip():
                ordered.append((default_model.strip(), "default_model"))
            if isinstance(candidates_list, list):
                for value in candidates_list:
                    text = str(value or "").strip()
                    if text:
                        ordered.append((text, "first_candidate"))

            model = None
            picked_from = None
            for candidate, reason in ordered:
                if candidate in blocked_models:
                    continue
                model = candidate
                picked_from = reason
                break

            meta = mapping.get("metadata") or {}
            temperature = meta.get("temperature") if isinstance(meta, dict) else None
            temp_value = None
            if isinstance(temperature, (int, float)):
                temp_value = float(temperature)
            return model, temp_value, picked_from

        for scope_type, scope_key, source in candidates:
            found = False
            active = False
            mapping_obj: dict[str, Any] | None = None

            if source == "prompt":
                mapping_obj = prompt_mapping
            else:
                if scope_key is not None:
                    record = await self._get_sqlite_mapping(scope_type, str(scope_key))
                    mapping_obj = record.get("mapping") if isinstance(record, dict) else None

            if isinstance(mapping_obj, dict):
                found = True
                active = bool(mapping_obj.get("is_active", True))

            chain.append(
                {
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "source": source,
                    "found": found,
                    "active": active,
                }
            )

            if not found or not active:
                continue

            model, temperature, picked_from = _pick(mapping_obj)
            if not model:
                return {
                    "model": None,
                    "temperature": temperature,
                    "hit": {"scope_type": scope_type, "scope_key": scope_key, "source": source},
                    "chain": chain,
                    "reason": "mapping_empty_or_blocked",
                }

            return {
                "model": model,
                "temperature": temperature,
                "hit": {"scope_type": scope_type, "scope_key": scope_key, "source": source, "picked_from": picked_from},
                "chain": chain,
                "reason": None,
            }

        return {"model": None, "temperature": None, "hit": None, "chain": chain, "reason": "mapping_not_found"}

    async def _ensure_sqlite_imported(self) -> None:
        if self._sqlite_import_done:
            return
        async with self._lock:
            if self._sqlite_import_done:
                return

            if self._sqlite_import_marker.exists():
                self._sqlite_import_done = True
                return

            try:
                row = await self._db.fetchone("SELECT COUNT(1) AS cnt FROM llm_model_mappings")
                if isinstance(row, dict) and int(row.get("cnt") or 0) > 0:
                    self._sqlite_import_marker.write_text(_utc_now(), encoding="utf-8")
                    self._sqlite_import_done = True
                    return
            except Exception:
                # 初始化失败不阻断启动；后续按“无导入”继续。
                pass

            if not self._legacy_file_path.exists():
                try:
                    self._sqlite_import_marker.write_text(_utc_now(), encoding="utf-8")
                except Exception:
                    pass
                self._sqlite_import_done = True
                return

            data = await self._read_legacy_fallback()
            imported = 0
            try:
                imported = await self._import_legacy_fallback_to_sqlite(data)
            except Exception:
                imported = 0

            if imported >= 0:
                try:
                    self._sqlite_import_marker.write_text(f"{_utc_now()} imported={imported}", encoding="utf-8")
                except Exception:
                    pass
                self._sqlite_import_done = True

    async def _read_blocked(self) -> dict[str, Any]:
        async with self._lock:
            return await self._read_blocked_unlocked()

    async def _read_blocked_unlocked(self) -> dict[str, Any]:
        if not self._blocked_file_path.exists():
            return {"updated_at": None, "blocked": []}
        try:
            raw = await asyncio.to_thread(self._blocked_file_path.read_text, "utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {"updated_at": None, "blocked": []}
        except Exception:
            return {"updated_at": None, "blocked": []}

    async def _collect_prompt_mappings(self) -> list[ModelMapping]:
        items: list[ModelMapping] = []
        page = 1
        page_size = 100
        while True:
            prompts, total = await self._ai_service.list_prompts(page=page, page_size=page_size)
            if not prompts:
                break
            for prompt in prompts:
                raw_tools = prompt.get("tools_json")
                mapping_data = None
                if isinstance(raw_tools, dict):
                    mapping_data = raw_tools.get(MAPPING_KEY)
                elif isinstance(raw_tools, list):
                    for entry in raw_tools:
                        if isinstance(entry, dict) and MAPPING_KEY in entry:
                            mapping_data = entry[MAPPING_KEY]
                            break
                if not mapping_data:
                    continue
                mapping = ModelMapping(
                    id=_mapping_id("prompt", str(prompt["id"])),
                    scope_type="prompt",
                    scope_key=str(prompt["id"]),
                    name=prompt.get("name"),
                    default_model=mapping_data.get("default_model"),
                    candidates=list(mapping_data.get("candidates") or []),
                    is_active=bool(mapping_data.get("is_active", True)),
                    updated_at=mapping_data.get("updated_at"),
                    source="prompt",
                    metadata={
                        "version": prompt.get("version"),
                        "category": prompt.get("category"),
                    },
                )
                items.append(mapping)
            # 使用 total + 分页参数作为终止条件，避免上游分页/映射缺失导致死循环
            if total and page * page_size >= total:
                break
            page += 1
        return items

    async def _read_prompt_mapping(self, prompt_id: int | None) -> dict[str, Any] | None:
        if prompt_id is None:
            return None
        try:
            prompt = await self._ai_service.get_prompt(int(prompt_id))
        except Exception:
            return None
        tools = prompt.get("tools_json")
        if isinstance(tools, dict):
            mapping = tools.get(MAPPING_KEY)
            return mapping if isinstance(mapping, dict) else None
        if isinstance(tools, list):
            for entry in tools:
                if isinstance(entry, dict) and MAPPING_KEY in entry and isinstance(entry[MAPPING_KEY], dict):
                    return entry[MAPPING_KEY]
        return None

    async def _collect_sqlite_mappings(
        self,
        *,
        scope_type: str | None = None,
        scope_key: str | None = None,
    ) -> list[ModelMapping]:
        query = "SELECT * FROM llm_model_mappings"
        params: list[Any] = []
        clauses: list[str] = []
        if scope_type:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_key:
            clauses.append("scope_key = ?")
            params.append(scope_key)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY COALESCE(updated_at, '') DESC"

        rows = await self._db.fetchall(query, params)
        items: list[ModelMapping] = []
        for row in rows:
            scope_type_value = _normalize_scope_type(row.get("scope_type"))
            scope_key_value = str(row.get("scope_key") or "").strip()
            if not scope_type_value or not scope_key_value:
                continue

            candidates: list[str] = []
            raw_candidates = row.get("candidates_json")
            if isinstance(raw_candidates, str) and raw_candidates.strip():
                try:
                    parsed = json.loads(raw_candidates)
                    if isinstance(parsed, list):
                        candidates = [str(v).strip() for v in parsed if str(v).strip()]
                except json.JSONDecodeError:
                    candidates = []

            metadata: dict[str, Any] = {}
            raw_meta = row.get("metadata_json")
            if isinstance(raw_meta, str) and raw_meta.strip():
                try:
                    parsed = json.loads(raw_meta)
                    if isinstance(parsed, dict):
                        metadata = parsed
                except json.JSONDecodeError:
                    metadata = {}

            default_model = row.get("default_model")
            default_text = str(default_model).strip() if isinstance(default_model, str) else None
            default_text = default_text if default_text else None

            mapping = ModelMapping(
                id=_mapping_id(scope_type_value, scope_key_value),
                scope_type=scope_type_value,
                scope_key=scope_key_value,
                name=row.get("name") if isinstance(row.get("name"), str) else None,
                default_model=default_text,
                candidates=candidates,
                is_active=bool(row.get("is_active", 1)),
                updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), str) else None,
                source="sqlite",
                metadata=metadata,
            )
            items.append(mapping)
        return items

    async def _write_prompt_mapping(self, prompt_id: int, mapping: dict[str, Any]) -> None:
        prompt = await self._ai_service.get_prompt(prompt_id)
        tools = prompt.get("tools_json")
        container: dict[str, Any]
        if isinstance(tools, dict):
            container = dict(tools)
        elif isinstance(tools, list):
            container = {"tools": tools}
        elif tools is None:
            container = {}
        else:
            container = {"raw": tools}
        container[MAPPING_KEY] = mapping
        await self._ai_service.update_prompt(prompt_id, {"tools_json": container})

    async def _upsert_sqlite_mapping(
        self,
        scope_type: str,
        scope_key: str,
        name: str | None,
        mapping: dict[str, Any],
    ) -> None:
        normalized_scope_type = _normalize_scope_type(scope_type)
        normalized_scope_key = str(scope_key or "").strip()
        if not normalized_scope_type or not normalized_scope_key:
            raise ValueError("invalid_mapping_scope")

        mapping_id = _mapping_id(normalized_scope_type, normalized_scope_key)
        candidates = mapping.get("candidates") if isinstance(mapping.get("candidates"), list) else []
        meta = mapping.get("metadata") if isinstance(mapping.get("metadata"), dict) else {}

        await self._db.execute(
            """
            INSERT INTO llm_model_mappings
            (id, scope_type, scope_key, name, default_model, candidates_json, is_active, updated_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              scope_type=excluded.scope_type,
              scope_key=excluded.scope_key,
              name=excluded.name,
              default_model=excluded.default_model,
              candidates_json=excluded.candidates_json,
              is_active=excluded.is_active,
              updated_at=excluded.updated_at,
              metadata_json=excluded.metadata_json
            """,
            (
                mapping_id,
                normalized_scope_type,
                normalized_scope_key,
                name,
                mapping.get("default_model"),
                json.dumps(candidates, ensure_ascii=False),
                1 if bool(mapping.get("is_active", True)) else 0,
                mapping.get("updated_at") or _utc_now(),
                json.dumps(meta, ensure_ascii=False),
            ),
        )

    async def _delete_sqlite_mapping(self, scope_type: str, scope_key: str) -> bool:
        normalized_scope_type = _normalize_scope_type(scope_type)
        normalized_scope_key = str(scope_key or "").strip()
        mapping_id = _mapping_id(normalized_scope_type, normalized_scope_key)
        existing = await self._db.fetchone("SELECT id FROM llm_model_mappings WHERE id = ?", (mapping_id,))
        if not existing:
            return False
        await self._db.execute("DELETE FROM llm_model_mappings WHERE id = ?", (mapping_id,))
        return True

    async def _get_sqlite_mapping(self, scope_type: str, scope_key: str) -> dict[str, Any] | None:
        normalized_scope_type = _normalize_scope_type(scope_type)
        normalized_scope_key = str(scope_key or "").strip()
        if not normalized_scope_type or not normalized_scope_key:
            return None

        mapping_id = _mapping_id(normalized_scope_type, normalized_scope_key)
        row = await self._db.fetchone("SELECT * FROM llm_model_mappings WHERE id = ?", (mapping_id,))
        if not row:
            return None

        candidates: list[str] = []
        raw_candidates = row.get("candidates_json")
        if isinstance(raw_candidates, str) and raw_candidates.strip():
            try:
                parsed = json.loads(raw_candidates)
                if isinstance(parsed, list):
                    candidates = [str(v).strip() for v in parsed if str(v).strip()]
            except json.JSONDecodeError:
                candidates = []

        metadata: dict[str, Any] = {}
        raw_meta = row.get("metadata_json")
        if isinstance(raw_meta, str) and raw_meta.strip():
            try:
                parsed = json.loads(raw_meta)
                if isinstance(parsed, dict):
                    metadata = parsed
            except json.JSONDecodeError:
                metadata = {}

        mapping = {
            "default_model": row.get("default_model"),
            "candidates": candidates,
            "is_active": bool(row.get("is_active", 1)),
            "updated_at": row.get("updated_at"),
            "metadata": metadata,
        }

        return {"name": row.get("name"), "mapping": mapping, "id": mapping_id, "scope_type": normalized_scope_type}

    async def _read_legacy_fallback(self) -> dict[str, dict[str, Any]]:
        text = await asyncio.to_thread(self._legacy_file_path.read_text, encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    async def _import_legacy_fallback_to_sqlite(self, data: dict[str, Any]) -> int:
        if not isinstance(data, dict):
            return 0
        imported = 0
        for raw_scope_type, scope_entries in data.items():
            scope_type = _normalize_scope_type(raw_scope_type)
            if not isinstance(scope_entries, dict):
                continue
            for raw_scope_key, payload in scope_entries.items():
                scope_key = str(raw_scope_key or "").strip()
                if not scope_key:
                    continue
                if not isinstance(payload, dict):
                    continue
                name = payload.get("name") if isinstance(payload.get("name"), str) else None
                mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else None
                if not isinstance(mapping, dict):
                    continue
                await self._upsert_sqlite_mapping(scope_type, scope_key, name, mapping)
                imported += 1
        return imported

    def _split_mapping_id(self, mapping_id: str) -> tuple[str, str]:
        if ":" not in mapping_id:
            raise ValueError("invalid_mapping_id")
        scope_type, scope_key = mapping_id.split(":", 1)
        if not scope_type or not scope_key:
            raise ValueError("invalid_mapping_id")
        return scope_type, scope_key


__all__ = ["ModelMappingService", "normalize_mapping_id", "normalize_scope_type"]
