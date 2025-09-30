"""指标收集与日志输出。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

from app.core.middleware import get_current_trace_id
from app.core.rate_limiter import get_rate_limiter
from app.core.sse_guard import get_sse_guard

logger = logging.getLogger(__name__)

# Prometheus指标定义
# 1. 认证请求总数（按状态和用户类型分类）
auth_requests_total = Counter(
    'auth_requests_total',
    'Total number of authentication requests',
    ['status', 'user_type']
)

# 2. 认证请求持续时间（按端点分类）
auth_request_duration_seconds = Histogram(
    'auth_request_duration_seconds',
    'Duration of authentication requests in seconds',
    ['endpoint']
)

# 3. JWT验证错误总数（按错误代码分类）
jwt_validation_errors_total = Counter(
    'jwt_validation_errors_total',
    'Total number of JWT validation errors',
    ['code']
)

# 4. JWKS缓存命中总数（按结果分类）
jwks_cache_hits_total = Counter(
    'jwks_cache_hits_total',
    'Total number of JWKS cache hits',
    ['result']  # hit, miss, error
)

# 5. 活跃连接数（Gauge类型）
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

# 6. 限流阻止总数（按原因分类）
rate_limit_blocks_total = Counter(
    'rate_limit_blocks_total',
    'Total number of rate limit blocks',
    ['reason', 'user_type']
)


@dataclass
class RateLimitMetrics:
    """限流指标。"""
    total_requests: int = 0
    blocked_requests: int = 0
    user_qps_blocks: int = 0
    user_daily_blocks: int = 0
    ip_qps_blocks: int = 0
    ip_daily_blocks: int = 0
    cooldown_blocks: int = 0
    anonymous_blocks: int = 0
    suspicious_ua_blocks: int = 0

    @property
    def block_rate(self) -> float:
        """阻止率百分比。"""
        if self.total_requests == 0:
            return 0.0
        return (self.blocked_requests / self.total_requests) * 100

    @property
    def success_rate(self) -> float:
        """成功率百分比。"""
        if self.total_requests == 0:
            return 100.0
        return ((self.total_requests - self.blocked_requests) / self.total_requests) * 100


@dataclass
class SSEMetrics:
    """SSE指标。"""
    total_connection_attempts: int = 0
    successful_connections: int = 0
    rejected_connections: int = 0
    user_limit_rejections: int = 0
    conversation_limit_rejections: int = 0
    active_connections: int = 0
    total_connection_time: float = 0.0

    @property
    def rejection_rate(self) -> float:
        """拒绝率百分比。"""
        if self.total_connection_attempts == 0:
            return 0.0
        return (self.rejected_connections / self.total_connection_attempts) * 100

    @property
    def success_rate(self) -> float:
        """成功率百分比。"""
        if self.total_connection_attempts == 0:
            return 100.0
        return (self.successful_connections / self.total_connection_attempts) * 100

    @property
    def avg_connection_duration(self) -> float:
        """平均连接时长（秒）。"""
        if self.successful_connections == 0:
            return 0.0
        return self.total_connection_time / self.successful_connections


class MetricsCollector:
    """指标收集器。"""

    def __init__(self):
        self.rate_limit_metrics = RateLimitMetrics()
        self.sse_metrics = SSEMetrics()
        self.start_time = time.time()
        self._metrics_task: Optional[asyncio.Task] = None
        self._start_metrics_task()

    def _start_metrics_task(self):
        """启动定期指标输出任务。"""
        async def output_metrics():
            while True:
                await asyncio.sleep(300)  # 5分钟输出一次
                await self.log_metrics()

        self._metrics_task = asyncio.create_task(output_metrics())

    async def log_metrics(self):
        """输出指标日志。"""
        try:
            # 收集限流器指标
            rate_limiter = get_rate_limiter()

            # 收集SSE守卫指标
            sse_guard = get_sse_guard()
            sse_stats = await sse_guard.get_stats()

            # 更新SSE指标
            self.sse_metrics.total_connection_attempts = sse_stats["total_created"] + sse_stats["total_rejected"]
            self.sse_metrics.successful_connections = sse_stats["total_created"]
            self.sse_metrics.rejected_connections = sse_stats["total_rejected"]
            self.sse_metrics.active_connections = sse_stats["active_connections"]

            rejection_reasons = sse_stats.get("rejection_reasons", {})
            self.sse_metrics.user_limit_rejections = rejection_reasons.get("user_limit_exceeded", 0)
            self.sse_metrics.conversation_limit_rejections = rejection_reasons.get("conversation_limit_exceeded", 0)

            # 计算运行时间
            uptime_seconds = time.time() - self.start_time
            uptime_hours = uptime_seconds / 3600

            # 构建指标报告
            metrics_report = {
                "timestamp": time.time(),
                "uptime_hours": round(uptime_hours, 2),
                "trace_id": get_current_trace_id(),
                "rate_limiting": {
                    "total_requests": self.rate_limit_metrics.total_requests,
                    "blocked_requests": self.rate_limit_metrics.blocked_requests,
                    "block_rate_percent": round(self.rate_limit_metrics.block_rate, 2),
                    "success_rate_percent": round(self.rate_limit_metrics.success_rate, 2),
                    "blocks_by_type": {
                        "user_qps": self.rate_limit_metrics.user_qps_blocks,
                        "user_daily": self.rate_limit_metrics.user_daily_blocks,
                        "ip_qps": self.rate_limit_metrics.ip_qps_blocks,
                        "ip_daily": self.rate_limit_metrics.ip_daily_blocks,
                        "cooldown": self.rate_limit_metrics.cooldown_blocks,
                        "anonymous": self.rate_limit_metrics.anonymous_blocks,
                        "suspicious_ua": self.rate_limit_metrics.suspicious_ua_blocks
                    }
                },
                "sse_concurrency": {
                    "total_attempts": self.sse_metrics.total_connection_attempts,
                    "successful_connections": self.sse_metrics.successful_connections,
                    "rejected_connections": self.sse_metrics.rejected_connections,
                    "rejection_rate_percent": round(self.sse_metrics.rejection_rate, 2),
                    "success_rate_percent": round(self.sse_metrics.success_rate, 2),
                    "active_connections": self.sse_metrics.active_connections,
                    "rejections_by_type": {
                        "user_limit": self.sse_metrics.user_limit_rejections,
                        "conversation_limit": self.sse_metrics.conversation_limit_rejections
                    }
                }
            }

            # 输出结构化日志
            logger.info(
                "系统指标报告 %s",
                json.dumps(metrics_report, ensure_ascii=False, separators=(',', ':'))
            )

            # 如果有异常情况，输出警告
            if self.rate_limit_metrics.block_rate > 20:
                logger.warning(
                    "限流阻止率过高 block_rate=%.2f%% trace_id=%s",
                    self.rate_limit_metrics.block_rate, get_current_trace_id()
                )

            if self.sse_metrics.rejection_rate > 10:
                logger.warning(
                    "SSE拒绝率过高 rejection_rate=%.2f%% trace_id=%s",
                    self.sse_metrics.rejection_rate, get_current_trace_id()
                )

        except Exception as e:
            logger.error(
                "指标收集失败 error=%s trace_id=%s",
                str(e), get_current_trace_id()
            )

    def record_rate_limit_request(self, blocked: bool, block_reason: Optional[str] = None):
        """记录限流请求。"""
        self.rate_limit_metrics.total_requests += 1

        if blocked:
            self.rate_limit_metrics.blocked_requests += 1

            # 按类型统计
            if block_reason:
                if "User QPS" in block_reason:
                    self.rate_limit_metrics.user_qps_blocks += 1
                elif "User daily" in block_reason:
                    self.rate_limit_metrics.user_daily_blocks += 1
                elif "IP QPS" in block_reason:
                    self.rate_limit_metrics.ip_qps_blocks += 1
                elif "IP daily" in block_reason:
                    self.rate_limit_metrics.ip_daily_blocks += 1
                elif "cooldown" in block_reason:
                    self.rate_limit_metrics.cooldown_blocks += 1

    def record_sse_attempt(self, successful: bool, rejection_reason: Optional[str] = None):
        """记录SSE连接尝试。"""
        self.sse_metrics.total_connection_attempts += 1

        if successful:
            self.sse_metrics.successful_connections += 1
        else:
            self.sse_metrics.rejected_connections += 1

            # 按类型统计
            if rejection_reason:
                if "User concurrent" in rejection_reason:
                    self.sse_metrics.user_limit_rejections += 1
                elif "Conversation concurrent" in rejection_reason:
                    self.sse_metrics.conversation_limit_rejections += 1

    def record_connection_duration(self, duration_seconds: float):
        """记录连接持续时间。"""
        self.sse_metrics.total_connection_time += duration_seconds

    async def get_current_metrics(self) -> Dict:
        """获取当前指标快照。"""
        sse_guard = get_sse_guard()
        sse_stats = await sse_guard.get_stats()

        return {
            "rate_limiting": asdict(self.rate_limit_metrics),
            "sse_concurrency": {
                **asdict(self.sse_metrics),
                "current_active": sse_stats["active_connections"],
                "current_users": sse_stats["active_users"],
                "current_conversations": sse_stats["active_conversations"]
            },
            "uptime_seconds": time.time() - self.start_time
        }


# 全局指标收集器实例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例。"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def log_rate_limit_hit(reason: str, user_id: Optional[str], client_ip: str):
    """记录限流命中的便捷函数。"""
    collector = get_metrics_collector()
    collector.record_rate_limit_request(blocked=True, block_reason=reason)

    logger.warning(
        "限流命中 reason=%s user_id=%s client_ip=%s trace_id=%s",
        reason, user_id, client_ip, get_current_trace_id()
    )


def log_sse_rejection(reason: str, user_id: str, conversation_id: Optional[str]):
    """记录SSE拒绝的便捷函数。"""
    collector = get_metrics_collector()
    collector.record_sse_attempt(successful=False, rejection_reason=reason)

    logger.warning(
        "SSE连接拒绝 reason=%s user_id=%s conversation_id=%s trace_id=%s",
        reason, user_id, conversation_id, get_current_trace_id()
    )


def log_cooldown_triggered(client_ip: str, failure_count: int, cooldown_seconds: int):
    """记录冷静期触发的便捷函数。"""
    logger.warning(
        "冷静期触发 client_ip=%s failure_count=%d cooldown_seconds=%d trace_id=%s",
        client_ip, failure_count, cooldown_seconds, get_current_trace_id()
    )
