"""SQLite 连接与表结构管理。"""
from __future__ import annotations

import asyncio
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
    is_active INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_prompts_is_active ON ai_prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_prompts_name ON ai_prompts(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_prompts_supabase_id ON ai_prompts(supabase_id);

CREATE TABLE IF NOT EXISTS ai_prompt_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    endpoint_id INTEGER NOT NULL,
    model TEXT,
    request_message TEXT NOT NULL,
    response_message TEXT,
    success INTEGER DEFAULT 0,
    latency_ms REAL,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(prompt_id) REFERENCES ai_prompts(id) ON DELETE CASCADE,
    FOREIGN KEY(endpoint_id) REFERENCES ai_endpoints(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_prompt_tests_prompt ON ai_prompt_tests(prompt_id);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_tests_endpoint ON ai_prompt_tests(endpoint_id);
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
                    "supabase_id": "ALTER TABLE ai_prompts ADD COLUMN supabase_id INTEGER",
                    "last_synced_at": "ALTER TABLE ai_prompts ADD COLUMN last_synced_at TEXT",
                },
            )
            await self._ensure_columns(
                "ai_prompt_tests",
                {
                    "latency_ms": "ALTER TABLE ai_prompt_tests ADD COLUMN latency_ms REAL",
                    "error": "ALTER TABLE ai_prompt_tests ADD COLUMN error TEXT",
                },
            )
            await self._conn.commit()

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

    async def _ensure_columns(self, table: str, ddl_map: dict[str, str]) -> None:
        if not ddl_map:
            return
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
