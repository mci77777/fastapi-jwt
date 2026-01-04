"""模型映射管理服务。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ai_config_service import AIConfigService

MAPPING_KEY = "__model_mapping"
BLOCKED_MODELS_KEY = "__blocked_models"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping_id(scope_type: str, scope_key: str) -> str:
    return f"{scope_type}:{scope_key}"


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
    """负责读取/写入 Prompt 及 fallback JSON 中的模型映射配置。"""

    def __init__(self, ai_service: AIConfigService, storage_dir: Path) -> None:
        self._ai_service = ai_service
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._storage_dir / "model_mappings.json"
        self._blocked_file_path = self._storage_dir / "blocked_models.json"
        self._lock = asyncio.Lock()

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
        prompt_mappings = await self._collect_prompt_mappings()
        fallback_mappings = await self._collect_fallback_mappings()
        combined: list[ModelMapping] = prompt_mappings + fallback_mappings
        if scope_type:
            combined = [item for item in combined if item.scope_type == scope_type]
        if scope_key:
            combined = [item for item in combined if item.scope_key == scope_key]
        return [item.to_dict() for item in combined]

    async def upsert_mapping(self, payload: dict[str, Any]) -> dict[str, Any]:
        scope_type = payload["scope_type"]
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
            await self._write_fallback_mapping(scope_type, scope_key, payload["name"], mapping)
        results = await self.list_mappings(scope_type=scope_type, scope_key=scope_key)
        return results[0] if results else {}

    async def ensure_minimal_global_mapping(self) -> dict[str, Any] | None:
        """当系统没有任何可用映射时，按当前端点配置生成一个最小 global 映射，保证 App 可选模型非空。"""

        existing = await self.list_mappings(scope_type="global", scope_key="global")
        if existing:
            return existing[0]

        endpoints, _ = await self._ai_service.list_endpoints(only_active=True, page=1, page_size=200)
        active = [ep for ep in endpoints if isinstance(ep, dict) and ep.get("is_active") and ep.get("has_api_key")]
        if not active:
            return None

        default_endpoint = next((ep for ep in active if ep.get("is_default")), active[0])
        blocked = set(await self.list_blocked_models())

        candidates: list[str] = []
        preferred = default_endpoint.get("model")
        if isinstance(preferred, str) and preferred.strip() and preferred.strip() not in blocked:
            candidates.append(preferred.strip())

        model_list = default_endpoint.get("model_list") or []
        if isinstance(model_list, list):
            for value in model_list:
                text = str(value or "").strip()
                if text and text not in blocked and text not in candidates:
                    candidates.append(text)

        # 兜底：从其他端点补齐少量候选，确保首屏至少可选 1 个
        if not candidates:
            for ep in active:
                text = str(ep.get("model") or "").strip()
                if text and text not in blocked and text not in candidates:
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

    async def activate_default(self, mapping_id: str, default_model: str) -> dict[str, Any]:
        scope_type, scope_key = self._split_mapping_id(mapping_id)
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
        """删除一条映射（prompt 映射写回 ai_prompts.tools_json；fallback 映射写回 JSON 文件）。"""

        scope_type, scope_key = self._split_mapping_id(mapping_id)

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

        async with self._lock:
            data = await self._read_fallback()
            bucket = data.get(scope_type)
            if not isinstance(bucket, dict) or scope_key not in bucket:
                return False
            bucket.pop(scope_key, None)
            if not bucket:
                data.pop(scope_type, None)
            await self._write_fallback(data)
            return True

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
        if ":" in key:
            mapping = next((m for m in mappings if m.get("id") == key and m.get("is_active", True)), None)
        else:
            # 兼容 App 业务 key（无 scope_type 前缀）：优先 tenant，其次 global
            scope_priority = ("tenant", "global")
            best: dict[str, Any] | None = None
            best_pri = 999
            best_updated = ""
            for item in mappings:
                if not isinstance(item, dict) or not item.get("is_active", True):
                    continue
                if str(item.get("scope_key") or "").strip() != key:
                    continue
                scope_type = str(item.get("scope_type") or "").strip()
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
            return {"resolved_model": candidate, "hit": True}

        # 命中映射但无可用模型：交给调用方做 fallback（避免把被屏蔽 key 直接打到上游）
        return {"resolved_model": None, "hit": True}

    async def sync_to_supabase(self, *, delete_missing: bool = False) -> dict[str, Any]:
        """把当前映射推送到 Supabase（若未配置 Supabase，则返回 skipped）。"""

        mappings = await self.list_mappings()
        return await self._ai_service.push_model_mappings_to_supabase(mappings, delete_missing=delete_missing)

    async def resolve_for_message(
        self,
        *,
        user_id: str,
        tenant_id: str | None = None,
        prompt_id: int | None = None,
    ) -> dict[str, Any]:
        """为一次 messages 请求解析模型选择（SSOT：prompt tools_json + fallback 文件）。

        优先级（越靠前越优先）：prompt → user → tenant → global。

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
        fallback = await self._read_fallback()

        candidates: list[tuple[str, str | None, str]] = []
        if prompt_id is not None:
            candidates.append(("prompt", str(prompt_id), "prompt"))
        candidates.append(("user", user_id, "fallback"))
        if tenant_id:
            candidates.append(("tenant", str(tenant_id), "fallback"))
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
                scope_bucket = fallback.get(scope_type) if isinstance(fallback, dict) else None
                if isinstance(scope_bucket, dict) and scope_key is not None:
                    payload = scope_bucket.get(str(scope_key))
                    if isinstance(payload, dict):
                        mapping_obj = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else None

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

    async def _collect_fallback_mappings(self) -> list[ModelMapping]:
        data = await self._read_fallback()
        mappings: list[ModelMapping] = []
        for scope_type, scope_entries in data.items():
            for scope_key, payload in scope_entries.items():
                mapping = payload.get("mapping") or {}
                mappings.append(
                    ModelMapping(
                        id=_mapping_id(scope_type, scope_key),
                        scope_type=scope_type,
                        scope_key=scope_key,
                        name=payload.get("name"),
                        default_model=mapping.get("default_model"),
                        candidates=list(mapping.get("candidates") or []),
                        is_active=bool(mapping.get("is_active", True)),
                        updated_at=mapping.get("updated_at"),
                        source="fallback",
                        metadata=mapping.get("metadata") or {},
                    )
                )
        return mappings

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

    async def _write_fallback_mapping(
        self,
        scope_type: str,
        scope_key: str,
        name: str | None,
        mapping: dict[str, Any],
    ) -> None:
        async with self._lock:
            data = await self._read_fallback()
            scope_bucket = data.setdefault(scope_type, {})
            scope_bucket[scope_key] = {
                "name": name,
                "mapping": mapping,
            }
            await self._write_fallback(data)

    async def _read_fallback(self) -> dict[str, dict[str, Any]]:
        if not self._file_path.exists():
            return {}
        text = await asyncio.to_thread(self._file_path.read_text, encoding="utf-8")
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        return {}

    async def _write_fallback(self, data: dict[str, Any]) -> None:
        await asyncio.to_thread(
            self._file_path.write_text,
            json.dumps(data, ensure_ascii=False, indent=2),
            "utf-8",
        )

    def _split_mapping_id(self, mapping_id: str) -> tuple[str, str]:
        if ":" not in mapping_id:
            raise ValueError("invalid_mapping_id")
        scope_type, scope_key = mapping_id.split(":", 1)
        if not scope_type or not scope_key:
            raise ValueError("invalid_mapping_id")
        return scope_type, scope_key


__all__ = ["ModelMappingService"]
