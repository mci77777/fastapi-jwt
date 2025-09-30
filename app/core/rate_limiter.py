"""限流器实现 - 令牌桶算法与滑动窗口。"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.auth import AuthenticatedUser, get_authenticated_user_optional
from app.core.exceptions import create_error_response
from app.core.middleware import get_current_trace_id
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """令牌桶实现。"""
    capacity: int
    tokens: float
    last_refill: float
    refill_rate: float  # tokens per second

    def __post_init__(self):
        if self.tokens > self.capacity:
            self.tokens = self.capacity

    def consume(self, tokens: int = 1) -> bool:
        """尝试消费令牌，返回是否成功。"""
        now = time.time()
        # 补充令牌
        time_passed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


@dataclass
class SlidingWindow:
    """滑动窗口计数器。"""
    window_size: int  # seconds
    max_requests: int
    requests: list = field(default_factory=list)

    def add_request(self) -> bool:
        """添加请求，返回是否在限制内。"""
        now = time.time()
        # 清理过期请求
        cutoff = now - self.window_size
        self.requests = [req_time for req_time in self.requests if req_time > cutoff]

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False


@dataclass
class CooldownTracker:
    """冷静期跟踪器。"""
    failure_count: int = 0
    last_failure: float = 0
    cooldown_until: float = 0

    def record_failure(self, cooldown_seconds: int, failure_threshold: int) -> None:
        """记录失败，可能触发冷静期。"""
        now = time.time()
        self.failure_count += 1
        self.last_failure = now

        if self.failure_count >= failure_threshold:
            self.cooldown_until = now + cooldown_seconds
            logger.warning(
                "触发冷静期 failure_count=%d cooldown_until=%f trace_id=%s",
                self.failure_count, self.cooldown_until, get_current_trace_id()
            )

    def is_in_cooldown(self) -> bool:
        """检查是否在冷静期。"""
        return time.time() < self.cooldown_until

    def reset(self) -> None:
        """重置计数器。"""
        self.failure_count = 0
        self.cooldown_until = 0


class RateLimiter:
    """限流器管理器。"""

    def __init__(self):
        self.settings = get_settings()
        # 用户限流 (user_id -> bucket)
        self.user_qps_buckets: Dict[str, TokenBucket] = {}
        self.user_daily_windows: Dict[str, SlidingWindow] = {}

        # IP限流 (ip -> bucket)
        self.ip_qps_buckets: Dict[str, TokenBucket] = {}
        self.ip_daily_windows: Dict[str, SlidingWindow] = {}

        # 冷静期跟踪 (ip -> tracker)
        self.cooldown_trackers: Dict[str, CooldownTracker] = defaultdict(CooldownTracker)

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """启动定期清理任务。"""
        async def cleanup():
            while True:
                await asyncio.sleep(300)  # 5分钟清理一次
                self._cleanup_old_entries()

        self._cleanup_task = asyncio.create_task(cleanup())

    def _cleanup_old_entries(self):
        """清理过期的限流条目。"""
        now = time.time()
        cutoff = now - 3600  # 1小时前的条目

        # 清理用户桶
        expired_users = [
            user_id for user_id, bucket in self.user_qps_buckets.items()
            if bucket.last_refill < cutoff
        ]
        for user_id in expired_users:
            self.user_qps_buckets.pop(user_id, None)
            self.user_daily_windows.pop(user_id, None)

        # 清理IP桶
        expired_ips = [
            ip for ip, bucket in self.ip_qps_buckets.items()
            if bucket.last_refill < cutoff
        ]
        for ip in expired_ips:
            self.ip_qps_buckets.pop(ip, None)
            self.ip_daily_windows.pop(ip, None)

        # 清理冷静期跟踪器
        expired_cooldowns = [
            ip for ip, tracker in self.cooldown_trackers.items()
            if tracker.last_failure < cutoff and not tracker.is_in_cooldown()
        ]
        for ip in expired_cooldowns:
            self.cooldown_trackers.pop(ip, None)

    def _get_user_qps_bucket(self, user_id: str, is_anonymous: bool = False) -> TokenBucket:
        """获取用户QPS令牌桶。"""
        if user_id not in self.user_qps_buckets:
            qps_limit = (
                self.settings.rate_limit_anonymous_qps if is_anonymous
                else self.settings.rate_limit_per_user_qps
            )
            self.user_qps_buckets[user_id] = TokenBucket(
                capacity=qps_limit,
                tokens=qps_limit,
                last_refill=time.time(),
                refill_rate=qps_limit
            )
        return self.user_qps_buckets[user_id]

    def _get_user_daily_window(self, user_id: str, is_anonymous: bool = False) -> SlidingWindow:
        """获取用户日限制滑动窗口。"""
        if user_id not in self.user_daily_windows:
            daily_limit = (
                self.settings.rate_limit_anonymous_daily if is_anonymous
                else self.settings.rate_limit_per_user_daily
            )
            self.user_daily_windows[user_id] = SlidingWindow(
                window_size=86400,  # 24小时
                max_requests=daily_limit
            )
        return self.user_daily_windows[user_id]

    def _get_ip_qps_bucket(self, ip: str, is_anonymous: bool = False) -> TokenBucket:
        """获取IP QPS令牌桶。"""
        if ip not in self.ip_qps_buckets:
            qps_limit = (
                self.settings.rate_limit_anonymous_qps if is_anonymous
                else self.settings.rate_limit_per_ip_qps
            )
            self.ip_qps_buckets[ip] = TokenBucket(
                capacity=qps_limit,
                tokens=qps_limit,
                last_refill=time.time(),
                refill_rate=qps_limit
            )
        return self.ip_qps_buckets[ip]

    def _get_ip_daily_window(self, ip: str) -> SlidingWindow:
        """获取IP日限制滑动窗口。"""
        if ip not in self.ip_daily_windows:
            self.ip_daily_windows[ip] = SlidingWindow(
                window_size=86400,  # 24小时
                max_requests=self.settings.rate_limit_per_ip_daily
            )
        return self.ip_daily_windows[ip]

    def check_rate_limit(self, user_id: Optional[str], client_ip: str, user_agent: str, user_type: str = "permanent") -> Tuple[bool, str, Optional[int]]:
        """
        检查限流状态。

        Args:
            user_id: 用户ID（如果已认证）
            client_ip: 客户端IP
            user_agent: 用户代理
            user_type: 用户类型（"anonymous" 或 "permanent"）

        Returns:
            (allowed, reason, retry_after_seconds)
        """
        # 检查冷静期
        cooldown_tracker = self.cooldown_trackers[client_ip]
        if cooldown_tracker.is_in_cooldown():
            retry_after = int(cooldown_tracker.cooldown_until - time.time())
            logger.warning(
                "请求被冷静期阻止 ip=%s retry_after=%d trace_id=%s",
                client_ip, retry_after, get_current_trace_id()
            )
            return False, "IP in cooldown period", retry_after

        # 检查异常UA和用户类型
        is_suspicious = self._is_suspicious_user_agent(user_agent)
        is_anonymous = user_type == "anonymous"

        # IP限流检查
        ip_qps_bucket = self._get_ip_qps_bucket(client_ip, is_anonymous or is_suspicious)
        if not ip_qps_bucket.consume():
            logger.warning(
                "IP QPS限流触发 ip=%s is_anonymous=%s is_suspicious=%s trace_id=%s",
                client_ip, is_anonymous, is_suspicious, get_current_trace_id()
            )
            return False, "IP QPS limit exceeded", 60

        ip_daily_window = self._get_ip_daily_window(client_ip)
        if not ip_daily_window.add_request():
            logger.warning(
                "IP日限制触发 ip=%s trace_id=%s",
                client_ip, get_current_trace_id()
            )
            return False, "IP daily limit exceeded", 3600

        # 用户限流检查（如果已认证）
        if user_id:
            user_qps_bucket = self._get_user_qps_bucket(user_id, is_anonymous)
            if not user_qps_bucket.consume():
                logger.warning(
                    "用户QPS限流触发 user_id=%s user_type=%s trace_id=%s",
                    user_id, user_type, get_current_trace_id()
                )
                return False, "User QPS limit exceeded", 60

            user_daily_window = self._get_user_daily_window(user_id, is_anonymous)
            if not user_daily_window.add_request():
                logger.warning(
                    "用户日限制触发 user_id=%s user_type=%s trace_id=%s",
                    user_id, user_type, get_current_trace_id()
                )
                return False, "User daily limit exceeded", 3600

        return True, "OK", None

    def record_failure(self, client_ip: str) -> None:
        """记录失败请求，可能触发冷静期。"""
        cooldown_tracker = self.cooldown_trackers[client_ip]
        cooldown_tracker.record_failure(
            self.settings.rate_limit_cooldown_seconds,
            self.settings.rate_limit_failure_threshold
        )

    def record_success(self, client_ip: str) -> None:
        """记录成功请求，重置失败计数。"""
        if client_ip in self.cooldown_trackers:
            self.cooldown_trackers[client_ip].reset()

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """检查是否为可疑的User-Agent。"""
        if not user_agent:
            return True

        user_agent_lower = user_agent.lower()
        suspicious_patterns = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget', 'python-requests',
            'postman', 'insomnia', 'httpie', 'test', 'monitor'
        ]

        return any(pattern in user_agent_lower for pattern in suspicious_patterns)


# 全局限流器实例
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """获取全局限流器实例。"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件。"""

    # 公共路由白名单（免限流）
    WHITELIST_PATHS = {
        "/api/v1/healthz",
        "/api/v1/livez",
        "/api/v1/readyz",
        "/api/v1/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        # 检查是否为白名单路径（免限流）
        if request.url.path in self.WHITELIST_PATHS:
            return await call_next(request)

        # 获取客户端信息
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # 获取用户信息（如果已认证）
        user = await get_authenticated_user_optional(request)
        user_id = user.uid if user else None
        user_type = user.user_type if user else "permanent"

        # 检查限流
        allowed, reason, retry_after = self.rate_limiter.check_rate_limit(
            user_id, client_ip, user_agent, user_type
        )

        if not allowed:
            # 记录限流命中
            logger.info(
                "限流命中 ip=%s user_id=%s user_type=%s reason=%s retry_after=%s trace_id=%s",
                client_ip, user_id, user_type, reason, retry_after, get_current_trace_id()
            )

            # 返回429错误
            headers = {}
            if retry_after:
                headers["Retry-After"] = str(retry_after)

            return create_error_response(
                status_code=429,
                code="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded: {reason}",
                headers=headers
            )

        # 执行请求
        response = await call_next(request)

        # 根据响应状态记录成功/失败
        if response.status_code >= 400:
            self.rate_limiter.record_failure(client_ip)
        else:
            self.rate_limiter.record_success(client_ip)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP。"""
        # 检查代理头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # 回退到直连IP
        return request.client.host if request.client else "unknown"
