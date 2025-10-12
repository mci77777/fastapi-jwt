"""Dashboard WebSocket 推送服务（Phase 1: 仅提供数据聚合接口）。"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class DashboardBroker:
    """管理 Dashboard 数据聚合（Phase 1: WebSocket 功能在 Phase 2 实现）。"""

    def __init__(self, metrics_collector: MetricsCollector) -> None:
        """初始化 DashboardBroker。

        Args:
            metrics_collector: 统计数据聚合服务
        """
        self.collector = metrics_collector
        logger.info("DashboardBroker initialized")

    async def get_dashboard_stats(self, time_window: str = "24h") -> Dict[str, Any]:
        """获取 Dashboard 统计数据。

        Args:
            time_window: 时间窗口 ("1h", "24h", "7d")

        Returns:
            聚合后的统计数据
        """
        return await self.collector.aggregate_stats(time_window)

