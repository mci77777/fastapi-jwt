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
        self._lock = asyncio.Lock()

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
            if len(items) >= total:
                break
            page += 1
        return items

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
