"""Dashboard 统计数据聚合服务。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

from app.core.metrics import auth_requests_total
from app.db.sqlite_manager import SQLiteManager
from app.services.monitor_service import EndpointMonitor
from app.services.model_mapping_service import ModelMappingService, normalize_scope_type
from app.services.llm_model_registry import LlmModelRegistry
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


class MetricsCollector:
    """聚合 Dashboard 统计数据，提供统一查询接口。"""

    def __init__(
        self,
        db_manager: SQLiteManager,
        endpoint_monitor: EndpointMonitor,
        model_mapping_service: Optional[ModelMappingService] = None,
        llm_model_registry: Optional[LlmModelRegistry] = None,
    ) -> None:
        self._db = db_manager
        self._monitor = endpoint_monitor
        self._mapping_service = model_mapping_service
        self._registry = llm_model_registry

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
            "mapped_models": await self._get_mapped_models_summary(),
            "e2e_mapped_models": await self._get_e2e_mapped_models_summary(),
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

    async def get_daily_active_users_series(self, days: int = 7) -> list[int]:
        """获取最近 N 天的日活用户数序列（按天粒度）。

        说明：当前仅在 Dashboard 图表使用，避免伪造 1h/24h 小时级曲线。
        返回长度为 days+1（包含今天）。
        """
        try:
            days_int = int(days or 0)
        except Exception:
            days_int = 0

        if days_int <= 0:
            return []

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_int)

        rows = await self._db.fetchall(
            """
            SELECT activity_date, COUNT(DISTINCT user_id) as total
            FROM user_activity_stats
            WHERE activity_date >= ?
            GROUP BY activity_date
            ORDER BY activity_date ASC
        """,
            [start_date.isoformat()],
        )

        by_date: dict[str, int] = {}
        for row in rows:
            date_key = row.get("activity_date")
            if not date_key:
                continue
            try:
                by_date[str(date_key)] = int(row.get("total") or 0)
            except Exception:
                by_date[str(date_key)] = 0

        values: list[int] = []
        for i in range(days_int, -1, -1):
            d = (end_date - timedelta(days=i)).isoformat()
            values.append(int(by_date.get(d, 0)))
        return values

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

    async def _get_mapped_models_summary(self) -> Dict[str, Any]:
        """聚合映射模型可用性摘要（Dashboard 展示用）。"""

        if not isinstance(self._mapping_service, ModelMappingService) or not isinstance(self._registry, LlmModelRegistry):
            return {"total": 0, "available": 0, "unavailable": 0, "availability_rate": 0.0}

        try:
            mappings = await self._mapping_service.list_mappings()
        except Exception:
            mappings = []

        scope_priority = ("mapping", "global")
        keys: set[str] = set()
        for item in mappings:
            if not isinstance(item, dict):
                continue
            scope_type = normalize_scope_type(item.get("scope_type"))
            if scope_type not in scope_priority:
                continue
            if not bool(item.get("is_active", True)):
                continue
            key = str(item.get("scope_key") or "").strip()
            if key:
                keys.add(key)

        total = len(keys)
        if total <= 0:
            return {"total": 0, "available": 0, "unavailable": 0, "availability_rate": 0.0}

        available = 0
        for key in sorted(keys):
            try:
                await self._registry.resolve_model_key(key)
                available += 1
            except Exception:
                continue

        unavailable = max(total - available, 0)
        availability_rate = round((available / total) * 100.0, 2) if total > 0 else 0.0
        return {
            "total": total,
            "available": available,
            "unavailable": unavailable,
            "availability_rate": availability_rate,
        }

    async def _get_e2e_mapped_models_summary(self) -> Dict[str, Any]:
        """读取最新 E2E 结果摘要（每日映射模型可用性）。"""

        def _parse_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
            if not row:
                return None
            raw_results = row.get("results_json")
            results: list[dict[str, Any]] = []
            if isinstance(raw_results, str) and raw_results.strip():
                try:
                    parsed = json.loads(raw_results)
                    if isinstance(parsed, list):
                        results = [item for item in parsed if isinstance(item, dict)]
                except Exception:
                    results = []
            return {
                "run_id": row.get("run_id"),
                "user_type": row.get("user_type"),
                "auth_mode": row.get("auth_mode"),
                "prompt_text": row.get("prompt_text"),
                "prompt_mode": row.get("prompt_mode"),
                "result_mode": row.get("result_mode"),
                "models_total": int(row.get("models_total") or 0),
                "models_success": int(row.get("models_success") or 0),
                "models_failed": int(row.get("models_failed") or 0),
                "started_at": row.get("started_at") or row.get("created_at"),
                "finished_at": row.get("finished_at"),
                "duration_ms": row.get("duration_ms"),
                "status": row.get("status"),
                "error_summary": row.get("error_summary"),
                "results": results,
            }

        latest: dict[str, Any] = {}
        for user_type in ("anonymous", "permanent"):
            row = await self._db.fetchone(
                """
                SELECT *
                FROM e2e_mapped_model_runs
                WHERE user_type = ?
                ORDER BY COALESCE(started_at, created_at) DESC
                LIMIT 1
                """,
                [user_type],
            )
            parsed = _parse_row(row)
            if parsed:
                latest[user_type] = parsed

        total_models = 0
        total_success = 0
        total_failed = 0
        for item in latest.values():
            if not isinstance(item, dict):
                continue
            total_models += int(item.get("models_total") or 0)
            total_success += int(item.get("models_success") or 0)
            total_failed += int(item.get("models_failed") or 0)

        success_rate = round((total_success / total_models) * 100.0, 2) if total_models > 0 else 0.0
        return {
            "latest": latest,
            "summary": {
                "models_total": total_models,
                "models_success": total_success,
                "models_failed": total_failed,
                "success_rate": success_rate,
            },
        }

    async def _get_api_connectivity(self) -> Dict[str, Any]:
        """查询 API 连通性状态。

        Returns:
            包含健康端点数、总端点数、连通率的字典
        """
        # 复用 EndpointMonitor 的状态快照；若从未检测过，则触发一次探针（非阻塞）以填充状态
        snapshot = self._monitor.snapshot()
        if not snapshot.get("last_run_at") and not snapshot.get("is_running") and not snapshot.get("probe_running"):
            try:
                self._monitor.trigger_probe()
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
