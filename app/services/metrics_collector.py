"""Dashboard 统计数据聚合服务。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.core.metrics import auth_requests_total
from app.db.sqlite_manager import SQLiteManager
from app.services.monitor_service import EndpointMonitor

logger = logging.getLogger(__name__)


class MetricsCollector:
    """聚合 Dashboard 统计数据，提供统一查询接口。"""

    def __init__(self, db_manager: SQLiteManager, endpoint_monitor: EndpointMonitor) -> None:
        self._db = db_manager
        self._monitor = endpoint_monitor

    async def aggregate_stats(self, time_window: str = "24h") -> Dict[str, Any]:
        """聚合所有统计数据。

        Args:
            time_window: 时间窗口 ("1h", "24h", "7d")

        Returns:
            包含所有统计指标的字典
        """
        return {
            "daily_active_users": await self._get_daily_active_users(time_window),
            "ai_requests": await self._get_ai_requests(time_window),
            "token_usage": None,  # 后续追加
            "api_connectivity": await self._get_api_connectivity(),
            "jwt_availability": await self._get_jwt_availability(),
        }

    async def _get_daily_active_users(self, time_window: str) -> int:
        """查询日活用户数。

        Args:
            time_window: 时间窗口

        Returns:
            活跃用户数
        """
        start_time = self._calculate_start_time(time_window)
        result = await self._db.fetchone(
            """
            SELECT COUNT(DISTINCT user_id) as total
            FROM user_activity_stats
            WHERE activity_date >= ?
        """,
            [start_time.date().isoformat()],
        )
        return result["total"] if result else 0

    async def _get_ai_requests(self, time_window: str) -> Dict[str, Any]:
        """查询 AI 请求统计。

        Args:
            time_window: 时间窗口

        Returns:
            包含总数、成功数、错误数、平均延迟的字典
        """
        start_time = self._calculate_start_time(time_window)
        result = await self._db.fetchone(
            """
            SELECT
                SUM(count) as total_count,
                SUM(success_count) as total_success,
                SUM(error_count) as total_error,
                AVG(total_latency_ms / NULLIF(count, 0)) as avg_latency
            FROM ai_request_stats
            WHERE request_date >= ?
        """,
            [start_time.date().isoformat()],
        )

        if not result or result["total_count"] is None:
            return {"total": 0, "success": 0, "error": 0, "avg_latency_ms": 0}

        return {
            "total": int(result["total_count"]),
            "success": int(result["total_success"] or 0),
            "error": int(result["total_error"] or 0),
            "avg_latency_ms": round(result["avg_latency"] or 0, 2),
        }

    async def _get_api_connectivity(self) -> Dict[str, Any]:
        """查询 API 连通性状态。

        Returns:
            包含健康端点数、总端点数、连通率的字典
        """
        # 复用 EndpointMonitor 的状态快照
        snapshot = self._monitor.snapshot()

        # 查询所有端点状态
        endpoints = await self._db.fetchall(
            """
            SELECT status FROM ai_endpoints WHERE is_active = 1
        """
        )

        total = len(endpoints)
        healthy = sum(1 for ep in endpoints if ep["status"] == "online")

        return {
            "is_running": snapshot["is_running"],
            "healthy_endpoints": healthy,
            "total_endpoints": total,
            "connectivity_rate": round(healthy / total * 100, 2) if total > 0 else 0,
            "last_check": snapshot["last_run_at"],
        }

    async def _get_jwt_availability(self) -> Dict[str, Any]:
        """查询 JWT 可获取性（从 Prometheus 指标计算）。

        Returns:
            包含成功率、总请求数、成功请求数的字典
        """
        # 从 Prometheus Counter 获取数据
        try:
            # 获取所有 auth_requests_total 指标
            total = 0
            success = 0

            # 使用 collect() 方法获取指标数据（正确的 Prometheus API）
            metrics_list = list(auth_requests_total.collect())
            logger.warning(f"[DEBUG] auth_requests_total.collect() returned {len(metrics_list)} metrics")

            for metric in metrics_list:
                logger.warning(f"[DEBUG] Metric: name={metric.name}, type={metric.type}, samples={len(metric.samples)}")
                for sample in metric.samples:
                    logger.warning(f"[DEBUG] Sample: name={sample.name}, labels={sample.labels}, value={sample.value}")
                    # sample.name: 指标名称（Counter 会自动添加 _total 后缀）
                    # sample.labels: 标签字典 {"status": "success", "user_type": "permanent"}
                    # sample.value: 指标值
                    # 注意：Prometheus Counter 的 sample.name 会自动添加 _total 后缀
                    # 例如：auth_requests_total{status="success",user_type="permanent"}
                    total += sample.value
                    if sample.labels.get("status") == "success":
                        success += sample.value

            logger.warning(f"[DEBUG] JWT availability: total={total}, success={success}")
            success_rate = (success / total * 100) if total > 0 else 0

            return {
                "success_rate": round(success_rate, 2),
                "total_requests": int(total),
                "successful_requests": int(success),
            }
        except Exception as exc:
            logger.warning("Failed to get JWT availability metrics: %s", exc)
            return {"success_rate": 0, "total_requests": 0, "successful_requests": 0}

    def _calculate_start_time(self, time_window: str) -> datetime:
        """计算时间窗口的起始时间。

        Args:
            time_window: 时间窗口字符串 ("1h", "24h", "7d")

        Returns:
            起始时间
        """
        now = datetime.now()

        if time_window == "1h":
            return now - timedelta(hours=1)
        elif time_window == "24h":
            return now - timedelta(hours=24)
        elif time_window == "7d":
            return now - timedelta(days=7)
        else:
            # 默认 24 小时
            return now - timedelta(hours=24)

