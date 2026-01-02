"""Dashboard 统计数据聚合服务。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from app.core.metrics import auth_requests_total
from app.db.sqlite_manager import SQLiteManager
from app.services.monitor_service import EndpointMonitor
from app.settings.config import get_settings

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
            "token_usage": await self._get_token_usage(time_window),
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
        # 复用 EndpointMonitor 的状态快照；若从未检测过，则按需跑一次以填充状态（不启动后台循环）
        snapshot = self._monitor.snapshot()
        if not snapshot.get("last_run_at") and not snapshot.get("is_running"):
            try:
                await self._monitor.run_once_now()
            except Exception:
                pass
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

    async def _get_token_usage(self, time_window: str) -> int:
        """统计 Token 使用量（从 conversation_logs.response_payload 解析 usage）。

        - OpenAI：usage.total_tokens
        - Claude：usage.input_tokens + usage.output_tokens（如存在）
        """
        start_time = self._calculate_start_time(time_window)
        rows = await self._db.fetchall(
            """
            SELECT response_payload
            FROM conversation_logs
            WHERE status = 'success' AND date(created_at) >= ?
        """,
            [start_time.date().isoformat()],
        )

        total_tokens = 0
        for row in rows:
            raw = row.get("response_payload")
            if not raw or not isinstance(raw, str):
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            usage = payload.get("usage")
            if not isinstance(usage, dict):
                continue

            if isinstance(usage.get("total_tokens"), int):
                total_tokens += int(usage["total_tokens"])
                continue

            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if isinstance(input_tokens, int) or isinstance(output_tokens, int):
                total_tokens += int(input_tokens or 0) + int(output_tokens or 0)

        return int(total_tokens)

    async def _get_jwt_availability(self) -> Dict[str, Any]:
        """查询 JWT 连通性（SSOT：JWKS 可用性 + 可选验证统计）。"""

        settings = get_settings()
        jwks_url = str(settings.supabase_jwks_url) if settings.supabase_jwks_url else ""

        probe_ok = False
        probe_error: str | None = None
        if jwks_url:
            try:
                async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                    resp = await client.get(jwks_url)
                    resp.raise_for_status()
                    data = resp.json()
                probe_ok = isinstance(data, dict) and isinstance(data.get("keys"), list) and len(data.get("keys") or []) > 0
                if not probe_ok:
                    probe_error = "jwks_invalid_payload"
            except Exception as exc:
                probe_error = str(exc)[:200]
        else:
            probe_error = "jwks_url_missing"

        # Prometheus：JWT 验证成功率（修复：Counter 会导出 *_created 时间戳，必须忽略）
        verification_total = 0.0
        verification_success = 0.0
        try:
            for metric in list(auth_requests_total.collect()):
                for sample in metric.samples:
                    if not sample.name.endswith("_total"):
                        continue
                    if not isinstance(sample.labels, dict) or "status" not in sample.labels:
                        continue
                    verification_total += float(sample.value or 0.0)
                    if sample.labels.get("status") == "success":
                        verification_success += float(sample.value or 0.0)
        except Exception:
            pass

        verification_success_rate = (
            round((verification_success / verification_total) * 100.0, 2) if verification_total > 0 else 0.0
        )

        return {
            # Dashboard 卡片使用的成功率：以 JWKS 探针为准（更贴近“JWT 连通性”）
            "success_rate": 100.0 if probe_ok else 0.0,
            "jwks_probe": {
                "configured": bool(jwks_url),
                "jwks_url": jwks_url or None,
                "ok": probe_ok,
                "error": probe_error,
            },
            # 兼容：保留 JWT 验证统计（用于趋势/排障）
            "verification": {
                "total_requests": int(verification_total),
                "successful_requests": int(verification_success),
                "success_rate": verification_success_rate,
            },
        }

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
