"""AI 端点与 Prompt 配置服务。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Optional

import httpx

from app.db import SQLiteManager
from app.settings.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT_PATHS = {
    "chat_completions": "/v1/chat/completions",
    "completions": "/v1/completions",
    "models": "/v1/models",
    "embeddings": "/v1/embeddings",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mask_api_key(api_key: Optional[str]) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}***{api_key[-4:]}"


def _safe_json_dumps(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _safe_json_loads(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


class AIConfigService:
    """封装 AI 端点与 Prompt 的本地持久化、状态检测及 Supabase 同步逻辑。"""

    def __init__(self, db: SQLiteManager, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    # --------------------------------------------------------------------- #
    # Endpoint 基础方法
    # --------------------------------------------------------------------- #
    def _build_resolved_endpoints(self, base_url: str) -> dict[str, str]:
        base = base_url.rstrip("/")
        return {name: f"{base}{path}" for name, path in DEFAULT_ENDPOINT_PATHS.items()}

    def _format_endpoint_row(self, row: dict[str, Any]) -> dict[str, Any]:
        model_list = _safe_json_loads(row.get("model_list")) or []
        resolved = _safe_json_loads(row.get("resolved_endpoints")) or {}
        return {
            "id": row["id"],
            "supabase_id": row.get("supabase_id"),
            "name": row["name"],
            "base_url": row["base_url"],
            "model": row.get("model"),
            "description": row.get("description"),
            "timeout": row.get("timeout", self._settings.http_timeout_seconds),
            "is_active": bool(row.get("is_active")),
            "is_default": bool(row.get("is_default")),
            "model_list": model_list,
            "status": row.get("status") or "unknown",
            "latency_ms": row.get("latency_ms"),
            "last_checked_at": row.get("last_checked_at"),
            "last_error": row.get("last_error"),
            "sync_status": row.get("sync_status") or "unsynced",
            "last_synced_at": row.get("last_synced_at"),
            "resolved_endpoints": resolved,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "api_key_masked": _mask_api_key(row.get("api_key")),
            "has_api_key": bool(row.get("api_key")),
        }

    async def list_endpoints(
        self,
        *,
        keyword: Optional[str] = None,
        only_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            clauses.append("(name LIKE ? OR base_url LIKE ? OR model LIKE ?)")
            fuzzy = f"%{keyword}%"
            params.extend([fuzzy, fuzzy, fuzzy])
        if only_active is not None:
            clauses.append("is_active = ?")
            params.append(1 if only_active else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_row = await self._db.fetchone(
            f"SELECT COUNT(1) AS count FROM ai_endpoints {where}",
            params,
        )
        query = (
            "SELECT * FROM ai_endpoints "
            f"{where} ORDER BY is_default DESC, updated_at DESC, id DESC "
            "LIMIT ? OFFSET ?"
        )
        rows = await self._db.fetchall(query, params + [page_size, (page - 1) * page_size])
        return [self._format_endpoint_row(row) for row in rows], int(total_row.get("count", 0))

    async def get_endpoint(self, endpoint_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE id = ?", [endpoint_id])
        if not row:
            raise ValueError("endpoint_not_found")
        return self._format_endpoint_row(row)

    async def _get_api_key(self, endpoint_id: int) -> Optional[str]:
        row = await self._db.fetchone("SELECT api_key FROM ai_endpoints WHERE id = ?", [endpoint_id])
        return row.get("api_key") if row else None

    async def create_endpoint(self, payload: dict[str, Any], *, auto_sync: bool = False) -> dict[str, Any]:
        now = _utc_now()
        if payload.get("is_default"):
            await self._db.execute("UPDATE ai_endpoints SET is_default = 0 WHERE is_default = 1")

        resolved = self._build_resolved_endpoints(payload["base_url"])
        await self._db.execute(
            """
            INSERT INTO ai_endpoints (
                name, base_url, model, description, api_key, timeout,
                is_active, is_default, model_list, status,
                latency_ms, last_checked_at, last_error,
                sync_status, last_synced_at, resolved_endpoints,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                payload["name"],
                payload["base_url"],
                payload.get("model"),
                payload.get("description"),
                payload.get("api_key"),
                payload.get("timeout") or int(self._settings.http_timeout_seconds),
                1 if payload.get("is_active", True) else 0,
                1 if payload.get("is_default") else 0,
                _safe_json_dumps(payload.get("model_list") or []),
                payload.get("status") or "unknown",
                payload.get("latency_ms"),
                payload.get("last_checked_at"),
                payload.get("last_error"),
                "pending_sync" if auto_sync else payload.get("sync_status", "unsynced"),
                payload.get("last_synced_at"),
                _safe_json_dumps(resolved),
                now,
                now,
            ],
        )
        row = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE id = last_insert_rowid()")
        endpoint = self._format_endpoint_row(row)
        if auto_sync:
            try:
                endpoint = await self.push_endpoint_to_supabase(endpoint["id"])
            except Exception:
                logger.exception("自动同步 Supabase 失败 endpoint_id=%s", endpoint["id"])
        return endpoint

    async def update_endpoint(self, endpoint_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get_endpoint(endpoint_id)

        updates: list[str] = []
        params: list[Any] = []

        def add(field: str, value: Any) -> None:
            updates.append(f"{field} = ?")
            params.append(value)

        if "name" in payload:
            add("name", payload["name"])
        if "base_url" in payload and payload["base_url"] != existing["base_url"]:
            add("base_url", payload["base_url"])
            add("resolved_endpoints", _safe_json_dumps(self._build_resolved_endpoints(payload["base_url"])))
        if "model" in payload:
            add("model", payload["model"])
        if "description" in payload:
            add("description", payload["description"])
        if "api_key" in payload:
            add("api_key", payload["api_key"])
        if "timeout" in payload:
            add("timeout", payload["timeout"])
        if "is_active" in payload:
            add("is_active", 1 if payload["is_active"] else 0)
        if "is_default" in payload:
            if payload["is_default"]:
                await self._db.execute(
                    "UPDATE ai_endpoints SET is_default = 0 WHERE is_default = 1 AND id != ?",
                    [endpoint_id],
                )
            add("is_default", 1 if payload["is_default"] else 0)
        if "model_list" in payload:
            add("model_list", _safe_json_dumps(payload["model_list"]))
        if "status" in payload:
            add("status", payload["status"])
        if "latency_ms" in payload:
            add("latency_ms", payload["latency_ms"])
        if "last_checked_at" in payload:
            add("last_checked_at", payload["last_checked_at"])
        if "last_error" in payload:
            add("last_error", payload["last_error"])
        if "sync_status" in payload:
            add("sync_status", payload["sync_status"])
        if "last_synced_at" in payload:
            add("last_synced_at", payload["last_synced_at"])

        if not updates:
            return existing

        add("updated_at", _utc_now())
        params.append(endpoint_id)
        await self._db.execute(f"UPDATE ai_endpoints SET {', '.join(updates)} WHERE id = ?", params)
        return await self.get_endpoint(endpoint_id)

    async def delete_endpoint(self, endpoint_id: int, *, sync_remote: bool = True) -> None:
        endpoint = await self.get_endpoint(endpoint_id)
        await self._db.execute("DELETE FROM ai_endpoints WHERE id = ?", [endpoint_id])

        if (
            sync_remote
            and endpoint.get("supabase_id")
            and self._supabase_available()
        ):
            headers = self._supabase_headers()
            base_url = self._supabase_base_url()
            try:
                async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
                    response = await client.delete(
                        f"{base_url}/ai_model?id=eq.{endpoint['supabase_id']}",
                        headers=headers,
                    )
                    response.raise_for_status()
            except httpx.HTTPError as exc:  # pragma: no cover
                logger.warning("删除 Supabase 端点失败 endpoint_id=%s error=%s", endpoint_id, exc)

    async def refresh_endpoint_status(self, endpoint_id: int) -> dict[str, Any]:
        endpoint = await self.get_endpoint(endpoint_id)
        headers = {"Content-Type": "application/json"}
        api_key = await self._get_api_key(endpoint_id)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        models_url = self._build_resolved_endpoints(endpoint["base_url"])["models"]
        timeout = endpoint["timeout"] or self._settings.http_timeout_seconds
        start = perf_counter()
        latency_ms: Optional[float] = None
        status_value = "checking"
        model_ids: list[str] = []
        error_text: Optional[str] = None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(models_url, headers=headers)
                latency_ms = (perf_counter() - start) * 1000
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            latency_ms = (perf_counter() - start) * 1000
            status_value = "offline"
            error_text = str(exc)
        else:
            items: list[Any]
            if isinstance(payload, dict):
                items = payload.get("data") or payload.get("models") or payload.get("items") or []
            elif isinstance(payload, list):
                items = payload
            else:
                items = []
            for item in items:
                if isinstance(item, dict) and "id" in item:
                    model_ids.append(str(item["id"]))
                elif isinstance(item, str):
                    model_ids.append(item)
            status_value = "online"

        await self.update_endpoint(
            endpoint_id,
            {
                "status": status_value,
                "latency_ms": latency_ms,
                "model_list": model_ids,
                "last_checked_at": _utc_now(),
                "last_error": error_text,
            },
        )
        return await self.get_endpoint(endpoint_id)

    async def refresh_all_status(self) -> list[dict[str, Any]]:
        rows = await self._db.fetchall("SELECT id FROM ai_endpoints ORDER BY id ASC")
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(await self.refresh_endpoint_status(row["id"]))
            except Exception:  # pragma: no cover
                logger.exception("检测端点状态失败 endpoint_id=%s", row["id"])
        return results

    # --------------------------------------------------------------------- #
    # Supabase 同步
    # --------------------------------------------------------------------- #
    def _supabase_available(self) -> bool:
        return bool(self._settings.supabase_project_id and self._settings.supabase_service_role_key)

    def _supabase_headers(self) -> dict[str, str]:
        if not self._supabase_available():
            raise RuntimeError("supabase_not_configured")
        key = self._settings.supabase_service_role_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _supabase_base_url(self) -> str:
        if not self._supabase_available():
            raise RuntimeError("supabase_not_configured")
        return f"https://{self._settings.supabase_project_id}.supabase.co/rest/v1"

    async def get_endpoint_by_supabase_id(self, supabase_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE supabase_id = ?", [supabase_id])
        if not row:
            raise ValueError("endpoint_not_found")
        return self._format_endpoint_row(row)

    async def push_endpoint_to_supabase(self, endpoint_id: int) -> dict[str, Any]:
        endpoint = await self.get_endpoint(endpoint_id)
        if not self._supabase_available():
            return endpoint

        payload = {
            "name": endpoint["name"],
            "model": endpoint.get("model"),
            "base_url": endpoint["base_url"],
            "description": endpoint.get("description"),
            "api_key": await self._get_api_key(endpoint_id),
            "timeout": endpoint["timeout"],
            "is_active": endpoint["is_active"],
            "is_default": endpoint["is_default"],
        }
        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        supabase_id = endpoint.get("supabase_id")

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            if supabase_id:
                response = await client.patch(
                    f"{base_url}/ai_model?id=eq.{supabase_id}",
                    headers=headers,
                    json=payload,
                )
            else:
                response = await client.post(
                    f"{base_url}/ai_model",
                    headers=headers,
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                supabase_row = data[0]
            elif isinstance(data, dict):
                supabase_row = data
            else:
                supabase_row = {}

        new_supabase_id = supabase_row.get("id") or supabase_id
        await self.update_endpoint(
            endpoint_id,
            {
                "supabase_id": new_supabase_id,
                "sync_status": "synced",
                "last_synced_at": _utc_now(),
            },
        )
        return await self.get_endpoint(endpoint_id)

    async def push_all_to_supabase(self) -> list[dict[str, Any]]:
        rows = await self._db.fetchall("SELECT id FROM ai_endpoints")
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(await self.push_endpoint_to_supabase(row["id"]))
            except Exception as exc:  # pragma: no cover
                logger.exception("同步端点失败 endpoint_id=%s", row["id"])
                await self.update_endpoint(
                    row["id"],
                    {"sync_status": f"error:{exc}", "last_synced_at": _utc_now()},
                )
        return results

    async def pull_endpoints_from_supabase(self) -> list[dict[str, Any]]:
        if not self._supabase_available():
            return []

        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.get(
                f"{base_url}/ai_model",
                headers=headers,
                params={"select": "*", "order": "updated_at.desc"},
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, list):
            return []

        merged: list[dict[str, Any]] = []
        for item in data:
            supabase_id = item.get("id")
            if not supabase_id:
                continue
            local = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE supabase_id = ?", [supabase_id])
            remote_updated = item.get("updated_at")
            if local and local.get("updated_at") and remote_updated:
                try:
                    local_time = datetime.fromisoformat(str(local["updated_at"]))
                    remote_time = datetime.fromisoformat(remote_updated.replace("Z", "+00:00"))
                    if local_time >= remote_time:
                        merged.append(self._format_endpoint_row(local))
                        continue
                except ValueError:
                    pass

            now = _utc_now()
            await self._db.execute(
                """
                INSERT INTO ai_endpoints (
                    supabase_id, name, base_url, model, description, api_key,
                    timeout, is_active, is_default, status, sync_status,
                    last_synced_at, resolved_endpoints, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supabase_id) DO UPDATE SET
                    name=excluded.name,
                    base_url=excluded.base_url,
                    model=excluded.model,
                    description=excluded.description,
                    api_key=excluded.api_key,
                    timeout=excluded.timeout,
                    is_active=excluded.is_active,
                    is_default=excluded.is_default,
                    status=excluded.status,
                    sync_status='synced',
                    last_synced_at=excluded.last_synced_at,
                    resolved_endpoints=excluded.resolved_endpoints,
                    updated_at=excluded.updated_at
                """,
                [
                    supabase_id,
                    item.get("name"),
                    item.get("base_url"),
                    item.get("model"),
                    item.get("description"),
                    item.get("api_key"),
                    item.get("timeout") or self._settings.http_timeout_seconds,
                    1 if item.get("is_active") else 0,
                    1 if item.get("is_default") else 0,
                    "unknown",
                    "synced",
                    _utc_now(),
                    _safe_json_dumps(self._build_resolved_endpoints(item.get("base_url", ""))),
                    now,
                    now,
                ],
            )
            merged.append(await self.get_endpoint_by_supabase_id(supabase_id))
        return merged

    async def supabase_status(self) -> dict[str, Any]:
        if not self._supabase_available():
            return {"status": "disabled", "detail": "Supabase 未配置"}

        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        status_value = "online"
        detail = "ok"
        latency_ms: Optional[float] = None

        start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
                response = await client.head(f"{base_url}/ai_model", headers=headers, params={"limit": 1})
                latency_ms = (perf_counter() - start) * 1000
                response.raise_for_status()
        except httpx.HTTPError as exc:
            latency_ms = (perf_counter() - start) * 1000
            status_value = "offline"
            detail = str(exc)

        last_synced = await self._db.fetchone(
            "SELECT MAX(last_synced_at) AS ts FROM ai_endpoints WHERE last_synced_at IS NOT NULL",
        )
        return {
            "status": status_value,
            "detail": detail,
            "latency_ms": latency_ms,
            "last_synced_at": last_synced.get("ts") if last_synced else None,
        }

    # --------------------------------------------------------------------- #
    # Prompt 管理
    # --------------------------------------------------------------------- #
    def _format_prompt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        tools = _safe_json_loads(row.get("tools_json"))
        return {
            "id": row["id"],
            "supabase_id": row.get("supabase_id"),
            "name": row["name"],
            "content": row["content"],
            "version": row.get("version"),
            "category": row.get("category"),
            "description": row.get("description"),
            "tools_json": tools,
            "is_active": bool(row.get("is_active")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    async def list_prompts(
        self,
        *,
        keyword: Optional[str] = None,
        only_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            clauses.append("(name LIKE ? OR content LIKE ? OR category LIKE ?)")
            fuzzy = f"%{keyword}%"
            params.extend([fuzzy, fuzzy, fuzzy])
        if only_active is not None:
            clauses.append("is_active = ?")
            params.append(1 if only_active else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_row = await self._db.fetchone(f"SELECT COUNT(1) AS count FROM ai_prompts {where}", params)
        rows = await self._db.fetchall(
            f"SELECT * FROM ai_prompts {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        )
        return [self._format_prompt_row(row) for row in rows], int(total_row.get("count", 0))

    async def get_prompt(self, prompt_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_prompts WHERE id = ?", [prompt_id])
        if not row:
            raise ValueError("prompt_not_found")
        return self._format_prompt_row(row)

    async def create_prompt(self, payload: dict[str, Any], *, auto_sync: bool = False) -> dict[str, Any]:
        now = _utc_now()
        if payload.get("is_active"):
            await self._db.execute("UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1")
        await self._db.execute(
            """
            INSERT INTO ai_prompts (
                name, content, version, category, description, tools_json,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            ,
            [
                payload["name"],
                payload["content"],
                payload.get("version"),
                payload.get("category"),
                payload.get("description"),
                _safe_json_dumps(payload.get("tools_json")),
                1 if payload.get("is_active") else 0,
                now,
                now,
            ],
        )
        row = await self._db.fetchone("SELECT * FROM ai_prompts WHERE id = last_insert_rowid()")
        prompt = self._format_prompt_row(row)
        if auto_sync:
            try:
                prompt = await self.push_prompt_to_supabase(prompt["id"])
            except Exception:
                logger.exception("自动同步 Prompt 到 Supabase 失败 prompt_id=%s", prompt["id"])
        return prompt

    async def update_prompt(self, prompt_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get_prompt(prompt_id)
        updates: list[str] = []
        params: list[Any] = []

        def add(field: str, value: Any) -> None:
            updates.append(f"{field} = ?")
            params.append(value)

        if "name" in payload:
            add("name", payload["name"])
        if "content" in payload:
            add("content", payload["content"])
        if "version" in payload:
            add("version", payload["version"])
        if "category" in payload:
            add("category", payload["category"])
        if "description" in payload:
            add("description", payload["description"])
        if "tools_json" in payload:
            add("tools_json", _safe_json_dumps(payload["tools_json"]))
        if "is_active" in payload:
            if payload["is_active"]:
                await self._db.execute(
                    "UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1 AND id != ?",
                    [prompt_id],
                )
            add("is_active", 1 if payload["is_active"] else 0)

        if not updates:
            return existing

        add("updated_at", _utc_now())
        params.append(prompt_id)
        await self._db.execute(f"UPDATE ai_prompts SET {', '.join(updates)} WHERE id = ?", params)
        return await self.get_prompt(prompt_id)

    async def delete_prompt(self, prompt_id: int, *, sync_remote: bool = True) -> None:
        prompt = await self.get_prompt(prompt_id)
        await self._db.execute("DELETE FROM ai_prompts WHERE id = ?", [prompt_id])

        if (
            sync_remote
            and prompt.get("supabase_id")
            and self._supabase_available()
        ):
            headers = self._supabase_headers()
            base_url = self._supabase_base_url()
            try:
                async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
                    response = await client.delete(
                        f"{base_url}/ai_prompt?id=eq.{prompt['supabase_id']}",
                        headers=headers,
                    )
                    response.raise_for_status()
            except httpx.HTTPError as exc:  # pragma: no cover
                logger.warning("删除 Supabase Prompt 失败 prompt_id=%s error=%s", prompt_id, exc)

    async def activate_prompt(self, prompt_id: int) -> dict[str, Any]:
        await self._db.execute("UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1 AND id != ?", [prompt_id])
        await self._db.execute(
            "UPDATE ai_prompts SET is_active = 1, updated_at = ? WHERE id = ?",
            [_utc_now(), prompt_id],
        )
        return await self.get_prompt(prompt_id)

    async def get_prompt_by_supabase_id(self, supabase_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_prompts WHERE supabase_id = ?", [supabase_id])
        if not row:
            raise ValueError("prompt_not_found")
        return self._format_prompt_row(row)

    async def push_prompt_to_supabase(self, prompt_id: int) -> dict[str, Any]:
        prompt = await self.get_prompt(prompt_id)
        if not self._supabase_available():
            return prompt

        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        payload = {
            "name": prompt["name"],
            "version": prompt.get("version") or "v1",
            "system_prompt": prompt["content"],
            "description": prompt.get("description"),
            "is_active": prompt["is_active"],
        }
        supabase_id = prompt.get("supabase_id")

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            if supabase_id:
                response = await client.patch(
                    f"{base_url}/ai_prompt?id=eq.{supabase_id}",
                    headers=headers,
                    json=payload,
                )
            else:
                response = await client.post(
                    f"{base_url}/ai_prompt",
                    headers=headers,
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                supabase_row = data[0]
            elif isinstance(data, dict):
                supabase_row = data
            else:
                supabase_row = {}

        await self._db.execute(
            "UPDATE ai_prompts SET supabase_id = ?, updated_at = ?, is_active = ?, last_synced_at = ? WHERE id = ?",
            [
                supabase_row.get("id") or supabase_id,
                _utc_now(),
                1 if prompt["is_active"] else 0,
                _utc_now(),
                prompt_id,
            ],
        )
        return await self.get_prompt(prompt_id)

    async def push_all_prompts_to_supabase(self) -> list[dict[str, Any]]:
        rows = await self._db.fetchall("SELECT id FROM ai_prompts")
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(await self.push_prompt_to_supabase(row["id"]))
            except Exception:  # pragma: no cover
                logger.exception("同步 Prompt 失败 prompt_id=%s", row["id"])
        return results

    async def pull_prompts_from_supabase(self) -> list[dict[str, Any]]:
        if not self._supabase_available():
            return []

        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.get(
                f"{base_url}/ai_prompt",
                headers=headers,
                params={"select": "*", "order": "updated_at.desc"},
            )
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, list):
            return []

        merged: list[dict[str, Any]] = []
        for item in data:
            supabase_id = item.get("id")
            if not supabase_id:
                continue
            local = await self._db.fetchone("SELECT * FROM ai_prompts WHERE supabase_id = ?", [supabase_id])
            remote_updated = item.get("updated_at")
            if local and local.get("updated_at") and remote_updated:
                try:
                    local_time = datetime.fromisoformat(str(local["updated_at"]))
                    remote_time = datetime.fromisoformat(remote_updated.replace("Z", "+00:00"))
                    if local_time >= remote_time:
                        merged.append(self._format_prompt_row(local))
                        continue
                except ValueError:
                    pass

            now = _utc_now()
            await self._db.execute(
                """
                INSERT INTO ai_prompts (
                    supabase_id, name, content, version, category, description, tools_json,
                    is_active, created_at, updated_at, last_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supabase_id) DO UPDATE SET
                    name=excluded.name,
                    content=excluded.content,
                    version=excluded.version,
                    category=excluded.category,
                    description=excluded.description,
                    tools_json=excluded.tools_json,
                    is_active=excluded.is_active,
                    updated_at=excluded.updated_at,
                    last_synced_at=excluded.last_synced_at
                """,
                [
                    supabase_id,
                    item.get("name"),
                    item.get("system_prompt"),
                    item.get("version"),
                    item.get("category"),
                    item.get("description"),
                    _safe_json_dumps(item.get("tools_json")),
                    1 if item.get("is_active") else 0,
                    now,
                    now,
                    _utc_now(),
                ],
            )
            merged.append(await self.get_prompt_by_supabase_id(supabase_id))
        return merged

    async def record_prompt_test(
        self,
        *,
        prompt_id: int,
        endpoint_id: int,
        model: Optional[str],
        request_message: str,
        response_message: Optional[str],
        success: bool,
        latency_ms: Optional[float],
        error: Optional[str],
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO ai_prompt_tests (
                prompt_id, endpoint_id, model, request_message, response_message,
                success, latency_ms, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                prompt_id,
                endpoint_id,
                model,
                request_message,
                response_message,
                1 if success else 0,
                latency_ms,
                error,
                _utc_now(),
            ],
        )

    async def list_prompt_tests(self, prompt_id: int, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self._db.fetchall(
            """
            SELECT * FROM ai_prompt_tests
            WHERE prompt_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [prompt_id, limit],
        )
        return [
            {
                "id": row["id"],
                "prompt_id": row["prompt_id"],
                "endpoint_id": row["endpoint_id"],
                "model": row.get("model"),
                "request_message": row.get("request_message"),
                "response_message": row.get("response_message"),
                "success": bool(row.get("success")),
                "latency_ms": row.get("latency_ms"),
                "error": row.get("error"),
                "created_at": row.get("created_at"),
            }
            for row in rows
        ]

    async def test_prompt(
        self,
        *,
        prompt_id: int,
        endpoint_id: int,
        message: str,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        prompt = await self.get_prompt(prompt_id)
        endpoint = await self.get_endpoint(endpoint_id)
        api_key = await self._get_api_key(endpoint_id)
        if not api_key:
            raise RuntimeError("endpoint_missing_api_key")

        selected_model = model or endpoint.get("model")
        model_candidates = endpoint.get("model_list") or []
        if not selected_model and model_candidates:
            selected_model = model_candidates[0]
        if not selected_model:
            selected_model = "gpt-4o-mini"

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": prompt["content"]},
                {"role": "user", "content": message},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        chat_url = self._build_resolved_endpoints(endpoint["base_url"])["chat_completions"]
        timeout = endpoint["timeout"] or self._settings.http_timeout_seconds

        start = perf_counter()
        latency_ms: Optional[float] = None
        response_payload: Optional[dict[str, Any]] = None
        reply_text = ""
        error_text: Optional[str] = None
        success = False

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(chat_url, headers=headers, json=payload)
                latency_ms = (perf_counter() - start) * 1000
                response.raise_for_status()
                response_payload = response.json()
                choices = response_payload.get("choices") if isinstance(response_payload, dict) else []
                if choices:
                    reply_text = choices[0].get("message", {}).get("content", "") or ""
                success = True
        except httpx.HTTPError as exc:
            latency_ms = (perf_counter() - start) * 1000
            error_text = str(exc)
            logger.error("Prompt 测试失败 prompt_id=%s endpoint_id=%s error=%s", prompt_id, endpoint_id, exc)
        except Exception as exc:  # pragma: no cover
            latency_ms = (perf_counter() - start) * 1000
            error_text = str(exc)
            logger.exception("Prompt 测试异常 prompt_id=%s endpoint_id=%s", prompt_id, endpoint_id)

        await self.record_prompt_test(
            prompt_id=prompt_id,
            endpoint_id=endpoint_id,
            model=selected_model,
            request_message=message,
            response_message=reply_text or (json.dumps(response_payload) if response_payload else None),
            success=success,
            latency_ms=latency_ms,
            error=error_text,
        )

        if not success:
            raise RuntimeError(error_text or "prompt_test_failed")

        return {
            "model": selected_model,
            "prompt": prompt["name"],
            "message": message,
            "response": reply_text,
            "usage": (response_payload or {}).get("usage") if response_payload else None,
            "latency_ms": latency_ms,
        }
