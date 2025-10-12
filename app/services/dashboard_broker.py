"""Dashboard WebSocket 推送服务。"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import WebSocket

from app.services.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class DashboardBroker:
    """管理 Dashboard WebSocket 连接和数据聚合。"""

    def __init__(self, metrics_collector: MetricsCollector) -> None:
        """初始化 DashboardBroker。

        Args:
            metrics_collector: 统计数据聚合服务
        """
        self.collector = metrics_collector
        self.connections: Dict[str, WebSocket] = {}  # {user_id: WebSocket}
        logger.info("DashboardBroker initialized")

    async def add_connection(self, user_id: str, websocket: WebSocket) -> None:
        """添加 WebSocket 连接。

        Args:
            user_id: 用户 ID
            websocket: WebSocket 连接对象
        """
        self.connections[user_id] = websocket
        logger.info("WebSocket connection added: user_id=%s total_connections=%d", user_id, len(self.connections))

    async def remove_connection(self, user_id: str) -> None:
        """移除 WebSocket 连接。

        Args:
            user_id: 用户 ID
        """
        if user_id in self.connections:
            self.connections.pop(user_id)
            logger.info(
                "WebSocket connection removed: user_id=%s total_connections=%d", user_id, len(self.connections)
            )

    def get_active_connections_count(self) -> int:
        """获取当前活跃连接数。

        Returns:
            活跃连接数
        """
        return len(self.connections)

    async def get_dashboard_stats(self, time_window: str = "24h") -> Dict[str, Any]:
        """获取 Dashboard 统计数据。

        Args:
            time_window: 时间窗口 ("1h", "24h", "7d")

        Returns:
            聚合后的统计数据
        """
        return await self.collector.aggregate_stats(time_window)
