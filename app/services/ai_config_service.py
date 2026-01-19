"""AI 端点与 Prompt 配置服务。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

_SUPPORTED_PROVIDER_PROTOCOLS: tuple[str, ...] = ("openai", "claude")

from app.db import SQLiteManager
from app.settings.config import Settings
from app.services.ai_url import build_resolved_endpoints, normalize_ai_base_url
from app.services.upstream_auth import is_retryable_auth_error, iter_auth_headers
from app.services.prompt_tools_assembly import assemble_system_prompt, extract_tools_schema, gate_active_tools_schema

logger = logging.getLogger(__name__)

DISALLOWED_TEST_ENDPOINT_PREFIXES = ("test-", "test_")

_VOYAGE_STATIC_MODEL_LIST: tuple[str, ...] = (
    # Text embeddings (from VoyageAI docs)
    "voyage-3.5",
    "voyage-3.5-lite",
    "voyage-3-large",
    "voyage-3",
    "voyage-3-lite",
    "voyage-code-3",
    "voyage-finance-2",
    "voyage-law-2",
    "voyage-code-2",
    "voyage-multilingual-2",
    "voyage-large-2-instruct",
    "voyage-large-2",
    "voyage-2",
    "voyage-lite-02-instruct",
    "voyage-02",
    "voyage-01",
    "voyage-lite-01",
    "voyage-lite-01-instruct",
)

_PERPLEXITY_STATIC_MODEL_LIST: tuple[str, ...] = (
    # Sonar family (from Perplexity docs)
    "sonar",
    "sonar-pro",
    "sonar-reasoning-pro",
    "sonar-deep-research",
)

_DEFAULT_SYSTEM_PROMPT_NAME = "gymbro-default-system-thinkingml-v45"
_DEFAULT_TOOLS_PROMPT_NAME = "gymbro-default-tools-v1"
_DEFAULT_SYSTEM_PROMPT_ASSET = Path("assets") / "prompts" / "serp_prompt.md"
_DEFAULT_TOOLS_PROMPT_ASSET = Path("assets") / "prompts" / "tool.md"

_DEFAULT_AGENT_SYSTEM_PROMPT_NAME = "gymbro-agent-system-thinkingml-v45"
_DEFAULT_AGENT_TOOLS_PROMPT_NAME = "gymbro-agent-tools-v1"
_DEFAULT_AGENT_SYSTEM_PROMPT_ASSET = _DEFAULT_SYSTEM_PROMPT_ASSET
_DEFAULT_AGENT_TOOLS_PROMPT_ASSET = Path("assets") / "prompts" / "agent_tool.md"

_PROMPT_TYPE_SYSTEM = "system"
_PROMPT_TYPE_TOOLS = "tools"
_PROMPT_TYPE_AGENT_SYSTEM = "agent_system"
_PROMPT_TYPE_AGENT_TOOLS = "agent_tools"
_ALLOWED_PROMPT_TYPES = {
    _PROMPT_TYPE_SYSTEM,
    _PROMPT_TYPE_TOOLS,
    _PROMPT_TYPE_AGENT_SYSTEM,
    _PROMPT_TYPE_AGENT_TOOLS,
}
_TOOLS_PROMPT_TYPES = {_PROMPT_TYPE_TOOLS, _PROMPT_TYPE_AGENT_TOOLS}
_AGENT_PROMPT_TYPES = {_PROMPT_TYPE_AGENT_SYSTEM, _PROMPT_TYPE_AGENT_TOOLS}

_TOOL_NAME_RE = re.compile(r"^\s*-\s*`([^`]+)`：\s*(.*)\s*$")
_TOOL_PARAMS_RE = re.compile(r"参数：\s*(.*)\s*$")


def _parse_tools_from_tool_md(tool_md: str) -> list[dict[str, Any]]:
    """从 tool.md 解析成 OpenAI tools schema（KISS：全部参数按 string 处理）。"""

    tools: list[dict[str, Any]] = []
    current_name: str | None = None
    current_desc: str = ""

    for raw_line in (tool_md or "").splitlines():
        line = raw_line.rstrip()
        m = _TOOL_NAME_RE.match(line)
        if m:
            current_name = str(m.group(1) or "").strip()
            current_desc = str(m.group(2) or "").strip()
            continue

        m = _TOOL_PARAMS_RE.search(line)
        if not m or not current_name:
            continue

        params_text = str(m.group(1) or "")
        params = [p.strip() for p in re.findall(r"`([^`]+)`", params_text) if str(p).strip()]
        properties = {p: {"type": "string", "description": p} for p in params}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": current_name,
                    "description": current_desc or f"GymBro tool: {current_name}",
                    "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
                },
            }
        )
        current_name = None
        current_desc = ""

    return tools


def _normalize_prompt_type(
    value: Any,
    *,
    tools_json_present: bool,
    existing_type: str | None = None,
) -> str:
    """Prompt 类型归一化（SSOT：system/tools + agent_system/agent_tools）。"""

    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_PROMPT_TYPES:
        return raw

    # 未显式指定时：保持与既有记录的 scope 一致（agent_* 不应被隐式降级为 system/tools）
    base_agent = str(existing_type or "").strip().lower() in _AGENT_PROMPT_TYPES
    if tools_json_present:
        return _PROMPT_TYPE_AGENT_TOOLS if base_agent else _PROMPT_TYPE_TOOLS
    return _PROMPT_TYPE_AGENT_SYSTEM if base_agent else _PROMPT_TYPE_SYSTEM


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


def _is_disallowed_test_endpoint_name(name: str | None) -> bool:
    text = (name or "").strip().lower()
    if not text:
        return False
    return text.startswith(DISALLOWED_TEST_ENDPOINT_PREFIXES)


class AIConfigService:
    """封装 AI 端点与 Prompt 的本地持久化、状态检测及 Supabase 同步逻辑。"""

    def __init__(self, db: SQLiteManager, settings: Settings, storage_dir: Path | None = None) -> None:
        self._db = db
        self._settings = settings
        self._storage_dir = (storage_dir or Path("storage") / "ai_runtime").resolve()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir = self._storage_dir / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------- #
    # Endpoint 基础方法
    # --------------------------------------------------------------------- #
    def _backup_latest_path(self, name: str) -> Path:
        return self._backup_dir / f"{name}-latest.json"

    def _backup_archive_path(self, name: str, slug: str) -> Path:
        return self._backup_dir / f"{name}-{slug}.json"

    def _list_backup_archives(self, name: str) -> list[Path]:
        return [path for path in self._backup_dir.glob(f"{name}-*.json") if not path.name.endswith("-latest.json")]

    async def _trim_backups(self, name: str, *, keep: int) -> None:
        archives = sorted(
            self._list_backup_archives(name),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for obsolete in archives[keep:]:
            try:
                obsolete.unlink(missing_ok=True)
            except OSError:
                logger.warning("删除备份文件失败 path=%s", obsolete)

    async def _write_backup(self, name: str, payload: Any, *, keep: int = 3) -> Path:
        exported_at = _utc_now()
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        content = {
            "exported_at": exported_at,
            "items": payload,
        }

        latest_path = self._backup_latest_path(name)
        archive_path = self._backup_archive_path(name, timestamp_slug)

        async def _write(path: Path) -> None:
            await asyncio.to_thread(
                path.write_text,
                json.dumps(content, ensure_ascii=False, indent=2),
                "utf-8",
            )

        await _write(latest_path)
        await _write(archive_path)
        await self._trim_backups(name, keep=keep)
        return latest_path

    async def write_backup(self, name: str, payload: Any, *, keep: int = 3) -> Path:
        """对外暴露的备份写入（用于跨服务复用同一备份目录/策略）。"""

        return await self._write_backup(name, payload, keep=keep)

    async def _collect_local_supabase_ids(self) -> set[int]:
        rows = await self._db.fetchall("SELECT supabase_id FROM ai_endpoints WHERE supabase_id IS NOT NULL")
        ids: set[int] = set()
        for row in rows:
            supabase_id = row.get("supabase_id")
            if supabase_id is None:
                continue
            try:
                ids.add(int(supabase_id))
            except (TypeError, ValueError):
                continue
        return ids

    async def _delete_missing_remote_models(
        self,
        *,
        keep_ids: set[int],
        remote_snapshot: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self._supabase_available():
            return
        data = remote_snapshot or await self._fetch_supabase_models()
        remote_ids = {int(item["id"]) for item in data if isinstance(item, dict) and item.get("id") is not None}
        to_delete = [sid for sid in remote_ids if sid not in keep_ids]
        for supabase_id in to_delete:
            try:
                await self._delete_supabase_endpoint(int(supabase_id))
            except Exception:  # pragma: no cover
                logger.exception("删除 Supabase 端点失败 supabase_id=%s", supabase_id)

    async def backup_local_endpoints(self) -> Path:
        rows = await self._db.fetchall("SELECT * FROM ai_endpoints ORDER BY id ASC")
        snapshot = [self._format_endpoint_row(row) for row in rows]
        return await self._write_backup("sqlite_endpoints", snapshot)

    async def backup_supabase_endpoints(self) -> Path | None:
        if not self._supabase_available():
            return None
        models = await self._fetch_supabase_models()
        return await self._write_backup("supabase_endpoints", models)

    def _build_resolved_endpoints(self, base_url: str) -> dict[str, str]:
        return build_resolved_endpoints(base_url)

    def _format_endpoint_row(self, row: dict[str, Any]) -> dict[str, Any]:
        model_list = _safe_json_loads(row.get("model_list")) or []
        resolved = _safe_json_loads(row.get("resolved_endpoints")) or {}
        provider_protocol = row.get("provider_protocol")
        if isinstance(provider_protocol, str) and provider_protocol.strip().lower() in _SUPPORTED_PROVIDER_PROTOCOLS:
            protocol_value = provider_protocol.strip().lower()
        else:
            # 兼容：历史数据/未配置时用最小启发式（不阻塞 UI 展示）
            base_url = str(row.get("base_url") or "").lower()
            name = str(row.get("name") or "").lower()
            protocol_value = "claude" if ("anthropic" in base_url or "claude" in name or "anthropic" in name) else "openai"

        return {
            "id": row["id"],
            "supabase_id": row.get("supabase_id"),
            "name": row["name"],
            "base_url": row["base_url"],
            "provider_protocol": protocol_value,
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
        total_count = int(total_row["count"]) if total_row and "count" in total_row else 0
        query = (
            "SELECT * FROM ai_endpoints "
            f"{where} ORDER BY is_default DESC, updated_at DESC, id DESC "
            "LIMIT ? OFFSET ?"
        )
        rows = await self._db.fetchall(query, params + [page_size, (page - 1) * page_size])
        return [self._format_endpoint_row(row) for row in rows], total_count

    async def get_endpoint(self, endpoint_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE id = ?", [endpoint_id])
        if not row:
            raise ValueError("endpoint_not_found")
        return self._format_endpoint_row(row)

    async def _get_api_key(self, endpoint_id: int) -> Optional[str]:
        row = await self._db.fetchone("SELECT api_key FROM ai_endpoints WHERE id = ?", [endpoint_id])
        return row.get("api_key") if row else None

    async def get_endpoint_api_key(self, endpoint_id: int) -> Optional[str]:
        """读取端点 API Key（严禁写入日志）。"""

        return await self._get_api_key(endpoint_id)

    async def create_endpoint(self, payload: dict[str, Any], *, auto_sync: bool = False) -> dict[str, Any]:
        now = _utc_now()
        if _is_disallowed_test_endpoint_name(payload.get("name")):
            raise ValueError("test_endpoint_name_not_allowed")
        if payload.get("is_default"):
            await self._db.execute("UPDATE ai_endpoints SET is_default = 0 WHERE is_default = 1")

        normalized_base_url = normalize_ai_base_url(payload["base_url"])
        resolved = self._build_resolved_endpoints(normalized_base_url)
        provider_protocol = str(payload.get("provider_protocol") or "").strip().lower()
        if provider_protocol not in _SUPPORTED_PROVIDER_PROTOCOLS:
            provider_protocol = "claude" if ("anthropic" in normalized_base_url.lower() or "claude" in str(payload.get("name") or "").lower()) else "openai"
        await self._db.execute(
            """
            INSERT INTO ai_endpoints (
                name, base_url, provider_protocol, model, description, api_key, timeout,
                is_active, is_default, model_list, status,
                latency_ms, last_checked_at, last_error,
                sync_status, last_synced_at, resolved_endpoints,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                payload["name"],
                normalized_base_url,
                provider_protocol,
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
        if row is None:
            raise RuntimeError("Failed to load endpoint after insert")
        endpoint = self._format_endpoint_row(row)
        if auto_sync:
            try:
                endpoint = await self.push_endpoint_to_supabase(endpoint["id"])
            except Exception:
                logger.exception("自动同步 Supabase 失败 endpoint_id=%s", endpoint["id"])
        return endpoint

    async def ensure_env_default_endpoint(self) -> Optional[dict[str, Any]]:
        """当本地无“可用端点”(active + 有 api_key + 非 offline) 时，用环境变量注入一个最小可用默认端点（用于本地 Docker/E2E）。"""

        # SSOT：生产环境端点必须来自“自定义配置”（SQLite 持久化）。
        # 仅在允许测试端点时，才启用 env-default 注入，避免“删不掉/回弹”与链路混乱。
        if not bool(getattr(self._settings, "allow_test_ai_endpoints", False)):
            return None

        row = await self._db.fetchone(
            """
            SELECT COUNT(1) AS cnt
            FROM ai_endpoints
            WHERE is_active = 1
              AND api_key IS NOT NULL
              AND TRIM(api_key) != ''
              AND (status IS NULL OR lower(status) != 'offline')
            """
        )
        count = int(row["cnt"]) if row and row.get("cnt") is not None else 0
        if count > 0:
            return None

        api_key = (self._settings.ai_api_key or "").strip()
        model = (self._settings.ai_model or "").strip()
        provider_raw = (self._settings.ai_provider or "").strip()
        provider = provider_raw.lower()
        base_url = str(self._settings.ai_api_base_url or "").strip()

        if not api_key or not model:
            return None

        if not base_url:
            # 兼容历史配置：AI_PROVIDER 可能被当作 OpenAI 兼容上游 base_url 填写
            if provider_raw.startswith("http://") or provider_raw.startswith("https://"):
                base_url = provider_raw
                provider = "openai"
            elif provider in ("openai",):
                base_url = "https://api.openai.com"
            elif provider in ("anthropic", "claude"):
                base_url = "https://api.anthropic.com"
            else:
                return None

        env_name = f"env-default-{provider or 'ai'}"

        # 幂等：若已有历史 env-default 端点（可能被手动置为 inactive），则复用并回写为 SSOT
        existing = await self._db.fetchone(
            """
            SELECT * FROM ai_endpoints
            WHERE lower(name) = lower(?)
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            [env_name],
        )
        if existing:
            endpoint = await self.update_endpoint(
                int(existing["id"]),
                {
                    "base_url": base_url,
                    "model": model,
                    "description": "Auto-seeded from env for local E2E",
                    "api_key": api_key,
                    "timeout": int(self._settings.http_timeout_seconds),
                    "is_active": True,
                    "is_default": True,
                    "status": "unknown",
                },
            )
        else:
            endpoint = await self.create_endpoint(
                {
                    "name": env_name,
                    "base_url": base_url,
                    "model": model,
                    "description": "Auto-seeded from env for local E2E",
                    "api_key": api_key,
                    "timeout": int(self._settings.http_timeout_seconds),
                    "is_active": True,
                    "is_default": True,
                    "status": "unknown",
                },
                auto_sync=False,
            )
        logger.info(
            "Seeded env default ai endpoint name=%s base_url=%s model=%s api_key=%s",
            endpoint.get("name"),
            endpoint.get("base_url"),
            endpoint.get("model"),
            _mask_api_key(api_key),
        )
        return endpoint

    async def ensure_default_prompts_seeded(self) -> dict[str, Any]:
        """启动期兜底：若缺失 active system/tools prompts，则从 assets/prompts 种子化（不覆盖已有配置）。"""

        created: dict[str, Any] = {}

        def _tool_schema_name(item: Any) -> str:
            if not isinstance(item, dict):
                return ""
            fn = item.get("function") if isinstance(item.get("function"), dict) else None
            name = fn.get("name") if isinstance(fn, dict) else None
            return str(name or "").strip()

        async def _maybe_patch_default_tools_prompt(
            active_prompt: dict[str, Any],
            desired_tools_json: Any,
            *,
            expected_name: str,
            expected_prompt_type: str,
        ) -> Optional[dict[str, Any]]:
            """为默认 tools prompt 做“仅追加”升级（不覆盖用户自定义 tools prompt）。"""

            if not isinstance(active_prompt, dict) or not desired_tools_json:
                return None
            if str(active_prompt.get("name") or "").strip() != expected_name:
                return None

            desired = extract_tools_schema(desired_tools_json) or []
            existing = extract_tools_schema(active_prompt.get("tools_json")) or []
            if not desired:
                return None

            existing_names = {_tool_schema_name(item) for item in existing if _tool_schema_name(item)}
            to_add = [item for item in desired if _tool_schema_name(item) and _tool_schema_name(item) not in existing_names]
            if not to_add:
                return None

            merged = list(existing) + to_add
            updated = await self.update_prompt(
                int(active_prompt["id"]),
                {"tools_json": merged, "prompt_type": expected_prompt_type},
            )
            # 保持 active（update_prompt 不会改变 is_active，但这里做一次幂等确保）
            updated = await self.activate_prompt(int(updated["id"]))
            return updated

        async def _ensure(
            *,
            prompt_type: str,
            name: str,
            asset_path: Path,
            tools_json: Any = None,
            content_override: str | None = None,
        ) -> Optional[dict[str, Any]]:
            active, _ = await self.list_prompts(only_active=True, prompt_type=prompt_type, page=1, page_size=1)
            if active:
                # 默认 tools prompt：允许“仅追加”补齐新工具 schema（例如 web_search.exa）。
                if prompt_type == "tools" and tools_json:
                    patched = await _maybe_patch_default_tools_prompt(
                        active[0],
                        tools_json,
                        expected_name=_DEFAULT_TOOLS_PROMPT_NAME,
                        expected_prompt_type=_PROMPT_TYPE_TOOLS,
                    )
                    if patched:
                        created["tools_prompt_patched"] = patched
                if prompt_type == _PROMPT_TYPE_AGENT_TOOLS and tools_json:
                    patched = await _maybe_patch_default_tools_prompt(
                        active[0],
                        tools_json,
                        expected_name=_DEFAULT_AGENT_TOOLS_PROMPT_NAME,
                        expected_prompt_type=_PROMPT_TYPE_AGENT_TOOLS,
                    )
                    if patched:
                        created["agent_tools_prompt_patched"] = patched
                return None

            row = await self._db.fetchone(
                """
                SELECT * FROM ai_prompts
                WHERE name = ? AND prompt_type = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                [name, prompt_type],
            )
            if row:
                prompt = self._format_prompt_row(row)
                updates: dict[str, Any] = {}
                if prompt_type == "tools" and not prompt.get("tools_json") and tools_json:
                    updates["tools_json"] = tools_json
                    updates["prompt_type"] = _PROMPT_TYPE_TOOLS
                if prompt_type == _PROMPT_TYPE_AGENT_TOOLS and not prompt.get("tools_json") and tools_json:
                    updates["tools_json"] = tools_json
                    updates["prompt_type"] = _PROMPT_TYPE_AGENT_TOOLS
                if updates:
                    prompt = await self.update_prompt(int(prompt["id"]), updates)
                prompt = await self.activate_prompt(int(prompt["id"]))
                return prompt

            if isinstance(content_override, str) and content_override.strip():
                content = content_override.strip()
            else:
                try:
                    content = asset_path.read_text(encoding="utf-8").strip()
                except Exception as exc:  # pragma: no cover
                    logger.warning("读取默认 Prompt 失败 path=%s error=%s", asset_path, exc)
                    return None
            if not content:
                return None

            return await self.create_prompt(
                {
                    "name": name,
                    "content": content,
                    "prompt_type": prompt_type,
                    "tools_json": tools_json,
                    "is_active": True,
                },
                auto_sync=False,
            )

        system_prompt = await _ensure(
            prompt_type="system",
            name=_DEFAULT_SYSTEM_PROMPT_NAME,
            asset_path=_DEFAULT_SYSTEM_PROMPT_ASSET,
        )
        if system_prompt:
            created["system_prompt"] = system_prompt

        tools_md = ""
        try:
            tools_md = _DEFAULT_TOOLS_PROMPT_ASSET.read_text(encoding="utf-8").strip()
        except Exception:
            tools_md = ""
        tools_schema = _parse_tools_from_tool_md(tools_md) if tools_md else []
        tools_prompt = await _ensure(
            prompt_type="tools",
            name=_DEFAULT_TOOLS_PROMPT_NAME,
            asset_path=_DEFAULT_TOOLS_PROMPT_ASSET,
            tools_json=tools_schema if tools_schema else None,
        )
        if tools_prompt:
            created["tools_prompt"] = tools_prompt

        # Agent prompts（与 /agent/runs 使用的 prompt 绑定；独立于 messages 的 system/tools）
        agent_system_seed = None
        try:
            base = _DEFAULT_AGENT_SYSTEM_PROMPT_ASSET.read_text(encoding="utf-8").strip()
            if base:
                agent_system_seed = (
                    "【Agent Run】你正在 GymBro Agent 模式下工作：\n"
                    "- 工具（Web 搜索/动作库检索）均由后端执行，结果会以 <gymbro_injected_context> 注入到用户消息中\n"
                    "- 你只可阅读其中 <text> 的内容，严禁在输出中复述/复制任何内部标签\n"
                    "- 无论是否有工具上下文，输出都必须严格满足 ThinkingML v4.5（<thinking>...</thinking><final>...</final>）\n"
                    "\n"
                    + base
                )
        except Exception:
            agent_system_seed = None

        agent_system_prompt = await _ensure(
            prompt_type=_PROMPT_TYPE_AGENT_SYSTEM,
            name=_DEFAULT_AGENT_SYSTEM_PROMPT_NAME,
            asset_path=_DEFAULT_AGENT_SYSTEM_PROMPT_ASSET,
            content_override=agent_system_seed,
        )
        if agent_system_prompt:
            created["agent_system_prompt"] = agent_system_prompt

        agent_tools_md = ""
        try:
            agent_tools_md = _DEFAULT_AGENT_TOOLS_PROMPT_ASSET.read_text(encoding="utf-8").strip()
        except Exception:
            agent_tools_md = ""
        agent_tools_schema = _parse_tools_from_tool_md(agent_tools_md) if agent_tools_md else []
        agent_tools_prompt = await _ensure(
            prompt_type=_PROMPT_TYPE_AGENT_TOOLS,
            name=_DEFAULT_AGENT_TOOLS_PROMPT_NAME,
            asset_path=_DEFAULT_AGENT_TOOLS_PROMPT_ASSET,
            tools_json=agent_tools_schema if agent_tools_schema else None,
        )
        if agent_tools_prompt:
            created["agent_tools_prompt"] = agent_tools_prompt

        return created

    async def update_endpoint(self, endpoint_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get_endpoint(endpoint_id)

        updates: list[str] = []
        params: list[Any] = []

        def add(field: str, value: Any) -> None:
            updates.append(f"{field} = ?")
            params.append(value)

        if "name" in payload:
            if _is_disallowed_test_endpoint_name(payload["name"]):
                raise ValueError("test_endpoint_name_not_allowed")
            add("name", payload["name"])
        if "provider_protocol" in payload:
            protocol = str(payload.get("provider_protocol") or "").strip().lower()
            if protocol and protocol not in _SUPPORTED_PROVIDER_PROTOCOLS:
                raise ValueError("provider_protocol_invalid")
            if protocol:
                add("provider_protocol", protocol)
        if "base_url" in payload:
            normalized_base_url = normalize_ai_base_url(payload["base_url"])
            computed_resolved = self._build_resolved_endpoints(normalized_base_url)
            if normalized_base_url != existing["base_url"]:
                add("base_url", normalized_base_url)
            # 允许在“规则升级/供应商适配”后，仅重算 resolved_endpoints（base_url 不变）。
            if computed_resolved != (existing.get("resolved_endpoints") or {}):
                add("resolved_endpoints", _safe_json_dumps(computed_resolved))
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
        if "supabase_id" in payload:
            add("supabase_id", payload["supabase_id"])

        if not updates:
            return existing

        add("updated_at", _utc_now())
        params.append(endpoint_id)
        await self._db.execute(f"UPDATE ai_endpoints SET {', '.join(updates)} WHERE id = ?", params)
        return await self.get_endpoint(endpoint_id)

    async def delete_endpoint(self, endpoint_id: int, *, sync_remote: bool = True) -> None:
        endpoint = await self.get_endpoint(endpoint_id)
        await self._db.execute("DELETE FROM ai_endpoints WHERE id = ?", [endpoint_id])

        if sync_remote and endpoint.get("supabase_id") and self._supabase_available():
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
        api_key = await self._get_api_key(endpoint_id)
        base_headers = {"Content-Type": "application/json"}
        auth_candidates = iter_auth_headers(api_key, endpoint.get("base_url") or "") if api_key else [{}]

        resolved_endpoints = self._build_resolved_endpoints(endpoint["base_url"])
        models_url = resolved_endpoints["models"]
        chat_url = resolved_endpoints["chat_completions"]
        embeddings_url = resolved_endpoints["embeddings"]
        timeout = endpoint["timeout"] or self._settings.http_timeout_seconds
        start = perf_counter()
        latency_ms: Optional[float] = None
        status_value = "checking"
        existing_model_list = endpoint.get("model_list") if isinstance(endpoint, dict) else None
        model_ids: list[str] = (
            [str(x) for x in existing_model_list if str(x).strip()]
            if isinstance(existing_model_list, list)
            else []
        )
        error_text: Optional[str] = None

        base_url_text = str(endpoint.get("base_url") or "").strip()
        endpoint_name = str(endpoint.get("name") or "").strip().lower()
        base_host = ""
        try:
            base_host = (urlsplit(base_url_text).hostname or "").strip().lower()
        except Exception:
            base_host = ""
        is_voyage = base_host == "api.voyageai.com" or "voyage" in endpoint_name
        is_perplexity = base_host == "api.perplexity.ai" or "perplexity" in endpoint_name

        try:
            response: httpx.Response | None = None
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 特例：VoyageAI 为 embeddings 供应商（chat/models 不适用）
                if is_voyage:
                    response = await client.options(embeddings_url, headers=base_headers)
                    latency_ms = (perf_counter() - start) * 1000
                    if response.status_code == 404:
                        status_value = "offline"
                        error_text = f"embeddings_not_found: {embeddings_url}"
                    elif response.status_code in (200, 204, 405):
                        status_value = "online"
                    elif response.status_code in (401, 403, 429):
                        status_value = "online"
                        error_text = f"embeddings_probe_status={response.status_code} url={embeddings_url}"
                    else:
                        status_value = "offline"
                        error_text = f"embeddings_probe_unexpected_status={response.status_code} url={embeddings_url}"

                    # VoyageAI 不提供 /models：用文档内置模型列表作为“可选项”展示（不影响 App chat 白名单）。
                    configured_model = str(endpoint.get("model") or "").strip()
                    merged: list[str] = []
                    if configured_model:
                        merged.append(configured_model)
                    merged.extend(model_ids)
                    merged.extend(list(_VOYAGE_STATIC_MODEL_LIST))
                    seen: set[str] = set()
                    model_ids = [item for item in merged if item and not (item in seen or seen.add(item))]
                # 特例：Perplexity 不提供 /models 列表，用 chat 端点探针 + 文档内置模型列表作为可选项
                elif is_perplexity:
                    response = await client.options(chat_url, headers=base_headers)
                    latency_ms = (perf_counter() - start) * 1000
                    if response.status_code == 404:
                        status_value = "offline"
                        error_text = f"chat_completions_not_found: {chat_url}"
                    elif response.status_code in (200, 204, 405):
                        status_value = "online"
                    elif response.status_code in (401, 403, 429):
                        status_value = "online"
                        error_text = f"chat_probe_status={response.status_code} url={chat_url}"
                    else:
                        status_value = "offline"
                        error_text = f"chat_probe_unexpected_status={response.status_code} url={chat_url}"

                    fetched: list[str] = []
                    try:
                        models_resp = await client.get(models_url, headers=base_headers)
                        if models_resp.status_code == 200:
                            payload = models_resp.json()
                            items: list[Any]
                            if isinstance(payload, dict):
                                items = payload.get("data") or payload.get("models") or payload.get("items") or []
                            elif isinstance(payload, list):
                                items = payload
                            else:
                                items = []
                            for item in items:
                                if isinstance(item, dict) and "id" in item:
                                    fetched.append(str(item["id"]))
                                elif isinstance(item, str):
                                    fetched.append(item)
                    except Exception:
                        fetched = []

                    configured_model = str(endpoint.get("model") or "").strip()
                    if fetched:
                        model_ids = fetched
                        if configured_model and configured_model not in model_ids:
                            model_ids = [configured_model] + model_ids
                    else:
                        merged = []
                        if configured_model:
                            merged.append(configured_model)
                        merged.extend(model_ids)
                        merged.extend(list(_PERPLEXITY_STATIC_MODEL_LIST))
                        seen: set[str] = set()
                        model_ids = [item for item in merged if item and not (item in seen or seen.add(item))]
                else:
                    configured_protocol = str(endpoint.get("provider_protocol") or "").strip().lower()
                    if configured_protocol not in _SUPPORTED_PROVIDER_PROTOCOLS:
                        configured_protocol = ""

                    base = normalize_ai_base_url(base_url_text)
                    openai_models_url = models_url
                    openai_chat_url = chat_url
                    claude_models_url = f"{base}/v1/models" if base else "/v1/models"
                    claude_messages_url = f"{base}/v1/messages" if base else "/v1/messages"

                    async def _probe_route(url: str) -> int:
                        probe_headers = dict(base_headers)
                        probe_resp = await client.options(url, headers=probe_headers)
                        if probe_resp.status_code == 404:
                            # 兼容：部分上游仅实现 POST（GET/HEAD 返回 404），用空 JSON 做“路由存在性”探测。
                            probe_resp = await client.post(url, headers=probe_headers, json={})
                        return int(probe_resp.status_code)

                    # 协议兜底：
                    # - 若用户显式配置 provider_protocol，则按该协议探测
                    # - 否则默认 OpenAI，404 再尝试 Claude(/v1/messages)
                    protocol = configured_protocol or "openai"
                    if protocol == "openai":
                        openai_probe_status = await _probe_route(openai_chat_url)
                        if openai_probe_status == 404 and not configured_protocol:
                            claude_probe_status = await _probe_route(claude_messages_url)
                            if claude_probe_status == 404:
                                status_value = "offline"
                                error_text = f"upstream_routes_not_found: openai={openai_chat_url} claude={claude_messages_url}"
                            else:
                                protocol = "claude"
                        elif openai_probe_status == 404 and configured_protocol:
                            status_value = "offline"
                            error_text = f"chat_completions_not_found: {openai_chat_url}"
                    else:
                        claude_probe_status = await _probe_route(claude_messages_url)
                        if claude_probe_status == 404:
                            status_value = "offline"
                            error_text = f"anthropic_messages_not_found: {claude_messages_url}"

                    if status_value != "offline" and protocol == "claude":
                        headers = {
                            "Content-Type": "application/json",
                        }
                        if api_key:
                            headers["x-api-key"] = api_key
                            headers["anthropic-version"] = "2023-06-01"
                        response = await client.get(claude_models_url, headers=headers)
                        latency_ms = (perf_counter() - start) * 1000
                    elif status_value != "offline":
                        for index, auth_headers in enumerate(auth_candidates):
                            headers = dict(base_headers)
                            headers.update(auth_headers)
                            response = await client.get(openai_models_url, headers=headers)
                            latency_ms = (perf_counter() - start) * 1000

                            if response.status_code != 401 or index >= len(auth_candidates) - 1:
                                break

                            payload: object | None = None
                            try:
                                payload = response.json()
                            except Exception:
                                payload = None

                            if not is_retryable_auth_error(response.status_code, payload):
                                break

                    if status_value == "offline":
                        response = None

                    if response is not None:
                        # 兼容性：401/403/405/429 多数表示“可达但需要鉴权/限流”，不应判定为 offline。
                        if response.status_code == 200:
                            payload = response.json()
                            items: list[Any]
                            if isinstance(payload, dict):
                                items = payload.get("data") or payload.get("models") or payload.get("items") or []
                            elif isinstance(payload, list):
                                items = payload
                            else:
                                items = []
                            fetched: list[str] = []
                            for item in items:
                                if isinstance(item, dict) and "id" in item:
                                    fetched.append(str(item["id"]))
                                elif isinstance(item, str):
                                    fetched.append(item)
                            if fetched:
                                model_ids = fetched
                            status_value = "online"
                        elif response.status_code == 404:
                            # 兼容性：部分上游不提供 /models 列表，但仍支持 chat/messages。
                            status_value = "online"
                            error_text = f"models_not_supported: {response.request.url}"

                            configured_model = str(endpoint.get("model") or "").strip()
                            if configured_model and configured_model not in model_ids:
                                model_ids = [configured_model] + model_ids
                        elif response.status_code in (401, 403, 405, 429):
                            status_value = "online"
                            detail = None
                            try:
                                payload = response.json()
                                if isinstance(payload, dict):
                                    detail = payload.get("error") or payload.get("message")
                            except Exception:
                                detail = None

                            suffix = ""
                            if isinstance(detail, str) and detail.strip():
                                safe_detail = detail.strip().replace("\n", " ")[:120]
                                suffix = f" detail={safe_detail}"
                            error_text = f"models_unavailable_status={response.status_code} url={response.request.url}{suffix}"
                        else:
                            status_value = "offline"
                            error_text = f"models_unexpected_status={response.status_code} url={response.request.url}"
        except httpx.HTTPError as exc:
            latency_ms = (perf_counter() - start) * 1000
            status_value = "offline"
            error_text = str(exc)

        await self.update_endpoint(
            endpoint_id,
            {
                # SSOT 修复：让 refresh 同时触发 resolved_endpoints 的重算（适配 Perplexity 等无 /v1 前缀上游）。
                "base_url": endpoint.get("base_url") or "",
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
        if not key:
            raise RuntimeError("supabase_not_configured")
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

    @staticmethod
    def _summarize_supabase_http_error(table: str, exc: httpx.HTTPStatusError) -> str:
        """将 Supabase HTTP 错误压缩为可诊断且不泄露敏感信息的消息。"""

        status_code = exc.response.status_code
        code: str | None = None
        message: str | None = None
        hint: str | None = None

        try:
            body = exc.response.json()
            if isinstance(body, dict):
                raw_code = body.get("code")
                if isinstance(raw_code, str) and raw_code.strip():
                    code = raw_code.strip()
                raw_message = body.get("message")
                if isinstance(raw_message, str) and raw_message.strip():
                    message = raw_message.strip()
                raw_hint = body.get("hint")
                if isinstance(raw_hint, str) and raw_hint.strip():
                    hint = raw_hint.strip()
        except Exception:  # pragma: no cover - 解析失败不影响主流程
            pass

        if not message:
            try:
                text = (exc.response.text or "").strip()
                if text:
                    message = text
            except Exception:  # pragma: no cover
                message = None

        parts = [f"Supabase 请求失败（table={table}，HTTP {status_code}）"]
        if code:
            parts.append(f"code={code}")
        if message:
            parts.append(f"message={message}")

        normalized_message = (message or "").lower()
        if status_code == 404 and ("schema cache" in normalized_message or f"public.{table}" in normalized_message):
            parts.append("建议：在 Supabase 执行 scripts/deployment/sql/create_ai_config_tables.sql 创建表后重试")
        elif status_code in (401, 403):
            parts.append("建议：检查 SUPABASE_SERVICE_ROLE_KEY 是否为 service_role，并确认 RLS 策略允许写入")
        elif hint:
            parts.append(f"hint={hint}")

        return "；".join(parts)

    async def _fetch_supabase_models(self) -> list[dict[str, Any]]:
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
        if isinstance(data, list):
            return data
        return []

    async def _fetch_supabase_model(self, supabase_id: int) -> Optional[dict[str, Any]]:
        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.get(
                f"{base_url}/ai_model",
                headers=headers,
                params={"id": f"eq.{supabase_id}", "limit": "1"},
            )
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data.get("id"):
            return data
        return None

    async def _delete_supabase_endpoint(self, supabase_id: int) -> None:
        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.delete(
                f"{base_url}/ai_model",
                headers=headers,
                params={"id": f"eq.{supabase_id}"},
            )
            response.raise_for_status()

    async def get_endpoint_by_supabase_id(self, supabase_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE supabase_id = ?", [supabase_id])
        if not row:
            raise ValueError("endpoint_not_found")
        return self._format_endpoint_row(row)

    async def push_endpoint_to_supabase(
        self,
        endpoint_id: int,
        *,
        overwrite: bool = True,
        delete_missing: bool = False,
        skip_backup: bool = False,
        remote_snapshot: Optional[dict[str, Any]] = None,
        remote_collection: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        endpoint = await self.get_endpoint(endpoint_id)
        if not self._supabase_available():
            return endpoint

        if not skip_backup:
            try:
                await self.backup_supabase_endpoints()
            except Exception:  # pragma: no cover - 备份失败不阻断同步
                logger.exception("备份 Supabase 端点失败，继续执行同步 endpoint_id=%s", endpoint_id)

        supabase_id = endpoint.get("supabase_id")
        remote_row = remote_snapshot
        if supabase_id:
            if remote_row is None and remote_collection:
                remote_row = next(
                    (item for item in remote_collection if str(item.get("id")) == str(supabase_id)),
                    None,
                )
            if remote_row is None:
                try:
                    remote_row = await self._fetch_supabase_model(int(supabase_id))
                except Exception:  # pragma: no cover - 读取远端失败不阻断
                    logger.warning("获取 Supabase 端点信息失败 supabase_id=%s", supabase_id)

        def _parse_dt(value: Any) -> Optional[datetime]:
            if not value:
                return None
            text = str(value)
            if text.endswith("Z"):
                text = text.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return None

        skip_remote_update = False
        if supabase_id and remote_row and not overwrite:
            local_updated = _parse_dt(endpoint.get("updated_at"))
            remote_updated = _parse_dt(remote_row.get("updated_at"))
            if remote_updated and (not local_updated or remote_updated >= local_updated):
                skip_remote_update = True

        if skip_remote_update:
            await self.update_endpoint(
                endpoint_id,
                {
                    "sync_status": "skipped:overwrite_disabled",
                    "last_synced_at": _utc_now(),
                },
            )
            updated_endpoint = await self.get_endpoint(endpoint_id)
        else:
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
            updated_endpoint = await self.get_endpoint(endpoint_id)

        if delete_missing:
            keep_ids = await self._collect_local_supabase_ids()
            await self._delete_missing_remote_models(
                keep_ids=keep_ids,
                remote_snapshot=remote_collection,
            )

        return updated_endpoint

    async def push_all_to_supabase(
        self,
        *,
        overwrite: bool = True,
        delete_missing: bool = False,
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetchall("SELECT id FROM ai_endpoints")
        if not rows:
            return []

        prefetched_remote: list[dict[str, Any]] = []
        if self._supabase_available():
            try:
                prefetched_remote = await self._fetch_supabase_models()
                await self._write_backup("supabase_endpoints", prefetched_remote)
            except Exception:  # pragma: no cover - 备份失败不影响主流程
                logger.exception("批量备份 Supabase 端点失败，继续执行推送")

        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(
                    await self.push_endpoint_to_supabase(
                        row["id"],
                        overwrite=overwrite,
                        delete_missing=False,
                        skip_backup=True,
                        remote_collection=prefetched_remote if prefetched_remote else None,
                    )
                )
            except Exception as exc:  # pragma: no cover
                logger.exception("同步端点失败 endpoint_id=%s", row["id"])
                await self.update_endpoint(
                    row["id"],
                    {"sync_status": f"error:{exc}", "last_synced_at": _utc_now()},
                )

        if delete_missing:
            keep_ids = await self._collect_local_supabase_ids()
            await self._delete_missing_remote_models(
                keep_ids=keep_ids,
                remote_snapshot=prefetched_remote,
            )

        return results

    async def pull_endpoints_from_supabase(
        self,
        *,
        overwrite: bool = False,
        delete_missing: bool = False,
    ) -> list[dict[str, Any]]:
        if not self._supabase_available():
            return []

        try:
            await self.backup_local_endpoints()
        except Exception:  # pragma: no cover - 备份失败不阻断拉取
            logger.exception("备份 SQLite 端点失败，继续执行拉取")

        data = await self._fetch_supabase_models()
        if not data:
            if delete_missing:
                await self._db.execute("DELETE FROM ai_endpoints WHERE supabase_id IS NOT NULL")
            return []

        merged: list[dict[str, Any]] = []
        seen_remote_ids: set[int] = set()

        for item in data:
            supabase_id = item.get("id")
            if not supabase_id:
                continue
            if _is_disallowed_test_endpoint_name(item.get("name")):
                continue
            seen_remote_ids.add(int(supabase_id))
            local = await self._db.fetchone("SELECT * FROM ai_endpoints WHERE supabase_id = ?", [supabase_id])
            remote_updated = item.get("updated_at")
            if not overwrite and local and local.get("updated_at") and remote_updated:
                try:
                    local_time = datetime.fromisoformat(str(local["updated_at"]))
                    remote_time = datetime.fromisoformat(remote_updated.replace("Z", "+00:00"))
                    if local_time >= remote_time:
                        merged.append(self._format_endpoint_row(local))
                        continue
                except ValueError:
                    pass

            now = _utc_now()
            inferred_protocol = "claude" if ("anthropic" in str(item.get("base_url") or "").lower() or "claude" in str(item.get("name") or "").lower()) else "openai"
            await self._db.execute(
                """
                INSERT INTO ai_endpoints (
                    supabase_id, name, base_url, provider_protocol, model, description, api_key,
                    timeout, is_active, is_default, status, sync_status,
                    last_synced_at, resolved_endpoints, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    inferred_protocol,
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
            merged_endpoint = await self.get_endpoint_by_supabase_id(supabase_id)
            merged.append(merged_endpoint)

            # Supabase ai_model 不存 model_list：同步后自动做一次连通性检测以拉取 /v1/models 并落盘 model_list，
            # 否则前端只能展示单个默认 model，难以进行真实对话测试。
            try:
                if not merged_endpoint.get("model_list"):
                    await self.refresh_endpoint_status(int(merged_endpoint["id"]))
            except Exception:  # pragma: no cover
                logger.exception("同步后刷新端点状态失败 endpoint_id=%s", merged_endpoint.get("id"))

        if delete_missing:
            if seen_remote_ids:
                placeholders = ",".join(["?"] * len(seen_remote_ids))
                await self._db.execute(
                    f"DELETE FROM ai_endpoints WHERE supabase_id IS NOT NULL AND supabase_id NOT IN ({placeholders})",
                    list(seen_remote_ids),
                )
            else:
                await self._db.execute("DELETE FROM ai_endpoints WHERE supabase_id IS NOT NULL")

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
        last_synced_at = last_synced.get("ts") if last_synced else None
        return {
            "status": status_value,
            "detail": detail,
            "latency_ms": latency_ms,
            "last_synced_at": last_synced_at,
        }

    # --------------------------------------------------------------------- #
    # Prompt 管理
    # --------------------------------------------------------------------- #
    def _format_prompt_row(self, row: dict[str, Any]) -> dict[str, Any]:
        tools = _safe_json_loads(row.get("tools_json"))
        prompt_type = row.get("prompt_type")
        if not isinstance(prompt_type, str) or not prompt_type.strip():
            prompt_type = "tools" if tools else "system"
        return {
            "id": row["id"],
            "supabase_id": row.get("supabase_id"),
            "name": row["name"],
            "content": row["content"],
            # 兼容：历史字段 system_prompt（content 为 SSOT）
            "system_prompt": row["content"],
            "version": row.get("version"),
            "category": row.get("category"),
            "description": row.get("description"),
            "tools_json": tools,
            # 兼容：部分客户端使用 tools 字段
            "tools": tools,
            "prompt_type": prompt_type,
            "is_active": bool(row.get("is_active")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    async def list_prompts(
        self,
        *,
        keyword: Optional[str] = None,
        only_active: Optional[bool] = None,
        prompt_type: Optional[str] = None,
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
        if prompt_type:
            clauses.append("prompt_type = ?")
            params.append(prompt_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_row = await self._db.fetchone(f"SELECT COUNT(1) AS count FROM ai_prompts {where}", params)
        total_count = int(total_row["count"]) if total_row and "count" in total_row else 0
        rows = await self._db.fetchall(
            f"SELECT * FROM ai_prompts {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        )
        return [self._format_prompt_row(row) for row in rows], total_count

    async def get_prompt(self, prompt_id: int) -> dict[str, Any]:
        row = await self._db.fetchone("SELECT * FROM ai_prompts WHERE id = ?", [prompt_id])
        if not row:
            raise ValueError("prompt_not_found")
        return self._format_prompt_row(row)

    async def create_prompt(self, payload: dict[str, Any], *, auto_sync: bool = False) -> dict[str, Any]:
        now = _utc_now()
        tools_value = payload.get("tools_json")
        prompt_type = _normalize_prompt_type(payload.get("prompt_type"), tools_json_present=bool(tools_value))

        if payload.get("is_active"):
            await self._db.execute(
                "UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1 AND prompt_type = ?",
                [prompt_type],
            )
        await self._db.execute(
            """
            INSERT INTO ai_prompts (
                name, content, version, category, description, tools_json,
                prompt_type, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                payload["name"],
                payload["content"],
                payload.get("version"),
                payload.get("category"),
                payload.get("description"),
                _safe_json_dumps(payload.get("tools_json")),
                prompt_type,
                1 if payload.get("is_active") else 0,
                now,
                now,
            ],
        )
        row = await self._db.fetchone("SELECT * FROM ai_prompts WHERE id = last_insert_rowid()")
        if row is None:
            raise RuntimeError("Failed to load prompt after insert")
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
        existing_type = existing.get("prompt_type") if isinstance(existing.get("prompt_type"), str) else None

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
            if "prompt_type" not in payload:
                payload["prompt_type"] = _normalize_prompt_type(
                    None,
                    tools_json_present=bool(payload.get("tools_json")),
                    existing_type=existing_type,
                )
        if "prompt_type" in payload:
            resolved_type = _normalize_prompt_type(
                payload.get("prompt_type"),
                tools_json_present=bool(payload.get("tools_json")) if "tools_json" in payload else bool(existing.get("tools_json")),
                existing_type=existing_type,
            )
            payload["prompt_type"] = resolved_type
            add("prompt_type", resolved_type)
        if "is_active" in payload:
            if payload["is_active"]:
                resolved_type = _normalize_prompt_type(
                    payload.get("prompt_type"),
                    tools_json_present=bool(payload.get("tools_json")) if "tools_json" in payload else bool(existing.get("tools_json")),
                    existing_type=existing_type,
                )
                await self._db.execute(
                    "UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1 AND id != ? AND prompt_type = ?",
                    [prompt_id, resolved_type],
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

        if sync_remote and prompt.get("supabase_id") and self._supabase_available():
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
        prompt = await self.get_prompt(prompt_id)
        resolved_type = _normalize_prompt_type(
            prompt.get("prompt_type"),
            tools_json_present=bool(prompt.get("tools_json")),
            existing_type=str(prompt.get("prompt_type") or "").strip(),
        )

        await self._db.execute(
            "UPDATE ai_prompts SET is_active = 0 WHERE is_active = 1 AND id != ? AND prompt_type = ?",
            [prompt_id, resolved_type],
        )
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
                    supabase_id, name, content, version, description, tools_json,
                    is_active, created_at, updated_at, last_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supabase_id) DO UPDATE SET
                    name=excluded.name,
                    content=excluded.content,
                    version=excluded.version,
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

    async def list_prompt_tests_by_run(self, run_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        pattern = f"%run_id={run_id}%"
        rows = await self._db.fetchall(
            """
            SELECT * FROM ai_prompt_tests
            WHERE request_message LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [pattern, limit],
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
        skip_prompt: bool = False,
        tool_choice: Any = None,
    ) -> dict[str, Any]:
        prompt = await self.get_prompt(prompt_id)
        raw_type = str(prompt.get("prompt_type") or "").strip().lower()
        tools_present = bool(prompt.get("tools_json"))
        prompt_type = _normalize_prompt_type(raw_type, tools_json_present=tools_present, existing_type=raw_type)

        if prompt_type == _PROMPT_TYPE_SYSTEM:
            other_type = _PROMPT_TYPE_TOOLS
        elif prompt_type == _PROMPT_TYPE_TOOLS:
            other_type = _PROMPT_TYPE_SYSTEM
        elif prompt_type == _PROMPT_TYPE_AGENT_SYSTEM:
            other_type = _PROMPT_TYPE_AGENT_TOOLS
        else:
            other_type = _PROMPT_TYPE_AGENT_SYSTEM

        system_prompt_text: Optional[str] = None
        tools_prompt_text: Optional[str] = None
        tools_json: Any = None

        if prompt_type in {_PROMPT_TYPE_SYSTEM, _PROMPT_TYPE_AGENT_SYSTEM}:
            system_prompt_text = str(prompt.get("content") or "").strip() or None
            if not skip_prompt:
                active_tools, _ = await self.list_prompts(only_active=True, prompt_type=other_type, page=1, page_size=1)
                if active_tools:
                    tools_prompt_text = str(active_tools[0].get("content") or "").strip() or None
                    tools_json = active_tools[0].get("tools_json")
        else:
            tools_prompt_text = str(prompt.get("content") or "").strip() or None
            tools_json = prompt.get("tools_json")
            if not skip_prompt:
                active_system, _ = await self.list_prompts(only_active=True, prompt_type=other_type, page=1, page_size=1)
                if active_system:
                    system_prompt_text = str(active_system[0].get("content") or "").strip() or None

        system_message = assemble_system_prompt(system_prompt_text, tools_prompt_text)

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

        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_message or "You are GymBro's AI assistant."},
                {"role": "user", "content": message},
            ],
        }

        tools_payload = extract_tools_schema(tools_json)
        # SSOT：与 /messages 一致（默认不执行 tool_calls）。
        # - 非 skip_prompt（server 组装）且未显式指定 tool_choice：不向上游发送 active tools schema。
        tools_payload = gate_active_tools_schema(
            tools_schema=tools_payload,
            tools_from_active_prompt=not bool(skip_prompt),
            tool_choice=tool_choice,
        )
        if tools_payload is not None:
            payload["tools"] = tools_payload
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
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
        except httpx.HTTPStatusError as exc:
            latency_ms = (perf_counter() - start) * 1000
            # 尝试获取响应体中的详细错误信息
            try:
                error_detail = exc.response.json()
                if isinstance(error_detail, dict):
                    # 提取常见的错误字段
                    error_msg = (
                        error_detail.get("error", {}).get("message")
                        or error_detail.get("message")
                        or error_detail.get("detail")
                        or str(exc)
                    )
                    error_text = f"{exc.response.status_code} {exc.response.reason_phrase}: {error_msg}"
                else:
                    error_text = f"{exc.response.status_code} {exc.response.reason_phrase}: {exc.response.text[:200]}"
            except Exception:
                error_text = str(exc)
            logger.error("Prompt 测试失败 prompt_id=%s endpoint_id=%s error=%s", prompt_id, endpoint_id, error_text)
        except httpx.HTTPError as exc:
            latency_ms = (perf_counter() - start) * 1000
            error_text = str(exc)
            logger.error("Prompt 测试网络错误 prompt_id=%s endpoint_id=%s error=%s", prompt_id, endpoint_id, exc)
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

    # --------------------------------------------------------------------- #
    # Supabase · Model Mappings（可选）
    # --------------------------------------------------------------------- #
    async def _fetch_supabase_model_mappings(self) -> list[dict[str, Any]]:
        headers = self._supabase_headers()
        base_url = self._supabase_base_url()
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.get(
                f"{base_url}/model_mappings",
                headers=headers,
                params={"select": "*", "order": "updated_at.desc"},
            )
            response.raise_for_status()
            data = response.json()
        return data if isinstance(data, list) else []

    async def fetch_model_mappings_from_supabase(self) -> list[dict[str, Any]]:
        """从 Supabase 拉取 model_mappings（仅返回数据，不做本地落库）。"""

        if not self._supabase_available():
            raise RuntimeError("supabase_not_configured")
        try:
            return await self._fetch_supabase_model_mappings()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._summarize_supabase_http_error("model_mappings", exc)) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"supabase_request_failed:{type(exc).__name__}") from exc

    async def push_model_mappings_to_supabase(
        self,
        mappings: list[dict[str, Any]],
        *,
        delete_missing: bool = False,
    ) -> dict[str, Any]:
        """把当前映射配置推送到 Supabase（若未配置 Supabase，则返回 skipped）。"""

        await self._write_backup("sqlite_model_mappings", mappings)

        if not self._supabase_available():
            return {"status": "skipped:supabase_not_configured", "synced_count": 0, "deleted_count": 0}

        remote_snapshot: list[dict[str, Any]] = []
        try:
            remote_snapshot = await self._fetch_supabase_model_mappings()
        except Exception:  # pragma: no cover
            remote_snapshot = []

        try:
            await self._write_backup("supabase_model_mappings", remote_snapshot)
        except Exception:  # pragma: no cover
            pass

        base_url = self._supabase_base_url()
        headers = dict(self._supabase_headers())
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"

        payload: list[dict[str, Any]] = []
        for item in mappings:
            if not isinstance(item, dict):
                continue
            mapping_id = item.get("id")
            if not isinstance(mapping_id, str) or not mapping_id.strip():
                continue
            payload.append(
                {
                    "id": mapping_id.strip(),
                    "scope_type": item.get("scope_type"),
                    "scope_key": item.get("scope_key"),
                    "name": item.get("name"),
                    "default_model": item.get("default_model"),
                    "candidates": item.get("candidates") or [],
                    "is_active": bool(item.get("is_active", True)),
                    "updated_at": item.get("updated_at"),
                    "source": item.get("source"),
                    "metadata": item.get("metadata") or {},
                }
            )

        synced_rows: list[dict[str, Any]] = []
        deleted_count = 0
        try:
            async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
                if payload:
                    response = await client.post(
                        f"{base_url}/model_mappings",
                        headers=headers,
                        params={"on_conflict": "id"},
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    synced_rows = data if isinstance(data, list) else []

                if delete_missing:
                    keep_ids = {row["id"] for row in payload if isinstance(row, dict) and isinstance(row.get("id"), str)}
                    remote_ids = {
                        str(row.get("id"))
                        for row in remote_snapshot
                        if isinstance(row, dict) and row.get("id") is not None
                    }
                    for obsolete_id in sorted(remote_ids - keep_ids):
                        resp = await client.delete(
                            f"{base_url}/model_mappings",
                            headers=headers,
                            params={"id": f"eq.{obsolete_id}"},
                        )
                        resp.raise_for_status()
                        deleted_count += 1
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._summarize_supabase_http_error("model_mappings", exc)) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"supabase_request_failed:{type(exc).__name__}") from exc

        return {
            "status": "synced",
            "synced_count": len(payload),
            "deleted_count": deleted_count,
            "remote_before": len(remote_snapshot),
            "remote_after": len(payload),
        }
