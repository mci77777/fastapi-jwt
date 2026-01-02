"""SQLite 连接与表结构管理。"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import aiosqlite
from fastapi import FastAPI

INIT_SCRIPT = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ai_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supabase_id INTEGER,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    model TEXT,
    api_key TEXT,
    description TEXT,
    timeout INTEGER DEFAULT 60,
    is_active INTEGER DEFAULT 1,
    is_default INTEGER DEFAULT 0,
    model_list TEXT,
    status TEXT DEFAULT 'unknown',
    latency_ms REAL,
    last_checked_at TEXT,
    last_error TEXT,
    sync_status TEXT DEFAULT 'unsynced',
    last_synced_at TEXT,
    resolved_endpoints TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_endpoints_is_active ON ai_endpoints(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_endpoints_status ON ai_endpoints(status);
CREATE INDEX IF NOT EXISTS idx_ai_endpoints_name ON ai_endpoints(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_endpoints_supabase_id ON ai_endpoints(supabase_id);

CREATE TABLE IF NOT EXISTS ai_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supabase_id INTEGER,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    version TEXT,
    category TEXT,
    description TEXT,
    tools_json TEXT,
    prompt_type TEXT DEFAULT 'system',
    is_active INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_prompts_is_active ON ai_prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_prompts_name ON ai_prompts(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_prompts_supabase_id ON ai_prompts(supabase_id);


CREATE TABLE IF NOT EXISTS dashboard_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,
    daily_active_users INTEGER DEFAULT 0,
    ai_request_count INTEGER DEFAULT 0,
    token_usage INTEGER DEFAULT 0,
    api_connectivity_rate REAL DEFAULT 0.0,
    jwt_availability_rate REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dashboard_stats_date ON dashboard_stats(stat_date);

CREATE TABLE IF NOT EXISTS user_activity_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_type TEXT NOT NULL,
    activity_date TEXT NOT NULL,
    request_count INTEGER DEFAULT 1,
    first_request_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_request_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, activity_date)
);

CREATE INDEX IF NOT EXISTS idx_user_activity_date ON user_activity_stats(activity_date);
CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity_stats(user_type);

CREATE TABLE IF NOT EXISTS ai_request_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    endpoint_id INTEGER,
    model TEXT,
    request_date TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    total_latency_ms REAL DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, endpoint_id, model, request_date),
    FOREIGN KEY(endpoint_id) REFERENCES ai_endpoints(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_request_date ON ai_request_stats(request_date);
CREATE INDEX IF NOT EXISTS idx_ai_request_endpoint ON ai_request_stats(endpoint_id);

CREATE TABLE IF NOT EXISTS conversation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    request_payload TEXT,
    response_payload TEXT,
    model_used TEXT,
    latency_ms REAL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_logs_created ON conversation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_logs_user ON conversation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_logs_status ON conversation_logs(status);

-- 本地 Dashboard 账号（仅用于本地 admin 登录与改密；不与 Supabase 用户混用）
CREATE TABLE IF NOT EXISTS local_users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Official Exercise Library snapshots (versioned seed payloads)
CREATE TABLE IF NOT EXISTS exercise_library_snapshots (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    generated_at INTEGER,
    total_count INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exercise_library_snapshots_created_at ON exercise_library_snapshots(created_at DESC);
"""


class SQLiteManager:
    """封装 aiosqlite 连接，负责表结构初始化与线程安全操作。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        return self._conn is not None

    async def init(self) -> None:
        if self._conn is not None:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        async with self._lock:
            try:
                await self._conn.executescript(INIT_SCRIPT)
            except sqlite3.DatabaseError as exc:
                if not self._looks_like_corruption(exc):
                    raise
                await self._recover_from_corruption()
                await self._conn.executescript(INIT_SCRIPT)
            await self._ensure_columns(
                "ai_endpoints",
                {
                    "model": "ALTER TABLE ai_endpoints ADD COLUMN model TEXT",
                    "description": "ALTER TABLE ai_endpoints ADD COLUMN description TEXT",
                    "latency_ms": "ALTER TABLE ai_endpoints ADD COLUMN latency_ms REAL",
                    "last_checked_at": "ALTER TABLE ai_endpoints ADD COLUMN last_checked_at TEXT",
                    "last_error": "ALTER TABLE ai_endpoints ADD COLUMN last_error TEXT",
                    "sync_status": "ALTER TABLE ai_endpoints ADD COLUMN sync_status TEXT DEFAULT 'unsynced'",
                    "last_synced_at": "ALTER TABLE ai_endpoints ADD COLUMN last_synced_at TEXT",
                    "resolved_endpoints": "ALTER TABLE ai_endpoints ADD COLUMN resolved_endpoints TEXT",
                    "supabase_id": "ALTER TABLE ai_endpoints ADD COLUMN supabase_id INTEGER",
                },
            )
            await self._ensure_columns(
                "ai_prompts",
                {
                    "version": "ALTER TABLE ai_prompts ADD COLUMN version TEXT",
                    "description": "ALTER TABLE ai_prompts ADD COLUMN description TEXT",
                    "tools_json": "ALTER TABLE ai_prompts ADD COLUMN tools_json TEXT",
                    "prompt_type": "ALTER TABLE ai_prompts ADD COLUMN prompt_type TEXT DEFAULT 'system'",
                    "supabase_id": "ALTER TABLE ai_prompts ADD COLUMN supabase_id INTEGER",
                    "last_synced_at": "ALTER TABLE ai_prompts ADD COLUMN last_synced_at TEXT",
                },
            )
            # 兼容：历史上没有 prompt_type 字段时，用 tools_json 是否非空推断 Tools Prompt。
            try:
                await self._conn.execute(
                    """
                    UPDATE ai_prompts
                    SET prompt_type = 'tools'
                    WHERE (prompt_type IS NULL OR TRIM(prompt_type) = '' OR prompt_type = 'system')
                      AND tools_json IS NOT NULL
                      AND TRIM(tools_json) NOT IN ('', 'null', '[]', '{}')
                    """,
                )
            except Exception:
                pass
            await self._conn.commit()

    @staticmethod
    def _looks_like_corruption(exc: BaseException) -> bool:
        msg = str(exc).lower()
        markers = (
            "database disk image is malformed",
            "malformed database schema",
            "file is not a database",
        )
        return any(marker in msg for marker in markers)

    async def _recover_from_corruption(self) -> None:
        # 备份旧 db（尽力而为），清理 -wal/-shm，truncate 后重连并初始化表结构。
        try:
            if self._conn is not None:
                await self._conn.close()
        finally:
            self._conn = None

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self._db_path.with_name(f"{self._db_path.name}.corrupt-{ts}")
        wal = self._db_path.with_name(f"{self._db_path.name}-wal")
        shm = self._db_path.with_name(f"{self._db_path.name}-shm")

        # bind mount 的文件在容器内可能无法 rename（EXDEV/busy），用 copy + truncate 保证可恢复。
        try:
            if self._db_path.exists() and self._db_path.is_file():
                shutil.copyfile(self._db_path, backup)
        except Exception:
            pass

        for sidecar in (wal, shm):
            try:
                if sidecar.exists():
                    sidecar.unlink()
            except Exception:
                pass

        try:
            if self._db_path.exists() and self._db_path.is_file():
                self._db_path.write_bytes(b"")
        except Exception:
            pass

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

    async def close(self) -> None:
        if self._conn is None:
            return
        async with self._lock:
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")
        async with self._lock:
            await self._conn.execute(query, tuple(params))
            await self._conn.commit()

    async def fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")
        async with self._lock:
            cursor = await self._conn.execute(query, tuple(params))
            row = await cursor.fetchone()
            await cursor.close()
        return dict(row) if row else None

    async def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")
        async with self._lock:
            cursor = await self._conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            await cursor.close()
        return [dict(row) for row in rows]

    async def log_conversation(
        self,
        user_id: str,
        message_id: str,
        request_payload: Optional[str],
        response_payload: Optional[str],
        model_used: Optional[str],
        latency_ms: float,
        status: str,
        error_message: Optional[str],
    ) -> None:
        """记录 AI 对话日志（循环缓冲区，最多保留 100 条）。

        Args:
            user_id: 用户 ID
            message_id: 消息 ID
            request_payload: 请求 payload（JSON 字符串）
            response_payload: 响应 payload（JSON 字符串）
            model_used: 使用的模型
            latency_ms: 延迟（毫秒）
            status: 状态（success/error）
            error_message: 错误信息
        """
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")

        async with self._lock:
            # 插入新记录
            await self._conn.execute(
                """
                INSERT INTO conversation_logs
                (user_id, message_id, request_payload, response_payload, model_used, latency_ms, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, message_id, request_payload, response_payload, model_used, latency_ms, status, error_message),
            )

            # 维护循环缓冲区：删除超过 100 条的旧记录
            await self._conn.execute(
                """
                DELETE FROM conversation_logs
                WHERE id NOT IN (
                    SELECT id FROM conversation_logs
                    ORDER BY id DESC
                    LIMIT 100
                )
                """
            )

            await self._conn.commit()

    async def get_conversation_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的对话日志。

        Args:
            limit: 返回记录数量上限（默认 100）

        Returns:
            日志记录列表
        """
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")

        async with self._lock:
            cursor = await self._conn.execute(
                """
                SELECT id, user_id, message_id, request_payload, response_payload,
                       model_used, latency_ms, status, error_message, created_at
                FROM conversation_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            await cursor.close()

        return [dict(row) for row in rows]

    async def patch_conversation_log_response_payload(self, message_id: str, patch: dict[str, Any]) -> None:
        """按 message_id 合并更新 response_payload（JSON）。

        说明：用于补齐 SSE 会话信息等“后置产生”的数据，避免依赖落盘日志。
        """
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")

        async with self._lock:
            cursor = await self._conn.execute(
                """
                SELECT id, response_payload
                FROM conversation_logs
                WHERE message_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (message_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()

            if not row:
                return

            record_id = row["id"]
            existing_raw = row["response_payload"]
            existing: dict[str, Any] = {}
            if isinstance(existing_raw, str) and existing_raw.strip():
                try:
                    parsed = json.loads(existing_raw)
                    if isinstance(parsed, dict):
                        existing = parsed
                except json.JSONDecodeError:
                    existing = {}

            merged = dict(existing)
            merged.update(patch or {})
            await self._conn.execute(
                """
                UPDATE conversation_logs
                SET response_payload = ?
                WHERE id = ?
                """,
                (json.dumps(merged, ensure_ascii=False), record_id),
            )
            await self._conn.commit()

    async def _ensure_columns(self, table: str, ddl_map: dict[str, str]) -> None:
        if not ddl_map:
            return
        if self._conn is None:
            raise RuntimeError("SQLiteManager has not been initialised.")
        cursor = await self._conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        await cursor.close()
        existing = {row["name"] for row in rows}
        for column, ddl in ddl_map.items():
            if column in existing:
                continue
            await self._conn.execute(ddl)


def get_sqlite_manager(app: FastAPI) -> SQLiteManager:
    """从 FastAPI app.state 取出 SQLiteManager。"""

    manager = getattr(app.state, "sqlite_manager", None)
    if manager is None:
        raise RuntimeError("SQLiteManager 未初始化，请检查应用启动流程。")
    return manager
