"""数据同步服务（Phase 1: 仅提供接口，Supabase 同步在后续阶段实现）。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.db.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)


class SyncService:
    """定时同步 SQLite 数据到 Supabase（Phase 1: 仅框架，实际同步逻辑待实现）。"""

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        """初始化 SyncService。

        Args:
            sqlite_manager: SQLite 数据库管理器
        """
        self._sqlite = sqlite_manager
        self._last_sync_time: Optional[datetime] = None
        logger.info("SyncService initialized (sync logic not implemented in Phase 1)")

    async def sync_dashboard_stats(self) -> None:
        """同步 dashboard_stats 表到 Supabase（Phase 1: 占位实现）。

        后续阶段将实现：
        1. 查询最近 1 小时数据
        2. 批量插入 Supabase
        3. 更新同步时间
        """
        logger.info("SyncService.sync_dashboard_stats called (no-op in Phase 1)")
        self._last_sync_time = datetime.now()

    @property
    def last_sync_time(self) -> Optional[datetime]:
        """获取最后同步时间。"""
        return self._last_sync_time

