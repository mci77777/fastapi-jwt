"""SSE 并发控制守卫。"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Set, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import AuthenticatedUser
from app.core.exceptions import create_error_response
from app.core.middleware import get_current_trace_id
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """连接信息。"""
    user_id: str
    conversation_id: Optional[str]
    message_id: str
    start_time: float
    client_ip: str
    user_agent: str


class SSEConcurrencyGuard:
    """SSE 并发控制守卫。"""

    def __init__(self):
        self.settings = get_settings()
        # 活跃连接跟踪
        self.active_connections: Dict[str, ConnectionInfo] = {}  # connection_id -> info
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)  # user_id -> connection_ids
        self.conversation_connections: Dict[str, Set[str]] = defaultdict(set)  # conversation_id -> connection_ids

        # 统计信息
        self.total_connections_created = 0
        self.total_connections_rejected = 0
        self.rejection_reasons: Dict[str, int] = defaultdict(int)

        # 锁保护
        self._lock = asyncio.Lock()

    async def check_and_register_connection(
        self,
        connection_id: str,
        user: AuthenticatedUser,
        conversation_id: Optional[str],
        message_id: str,
        client_ip: str,
        user_agent: str
    ) -> tuple[bool, str, Optional[int]]:
        """
        检查并注册SSE连接。

        Returns:
            (allowed, reason, retry_after_seconds)
        """
        async with self._lock:
            user_id = user.uid

            # 检查用户并发限制（根据用户类型设置不同限制）
            user_connection_count = len(self.user_connections.get(user_id, set()))
            is_anonymous = user.user_type == "anonymous"
            max_concurrent = (
                self.settings.sse_max_concurrent_per_anonymous_user if is_anonymous
                else self.settings.sse_max_concurrent_per_user
            )

            if user_connection_count >= max_concurrent:
                self.total_connections_rejected += 1
                self.rejection_reasons["user_limit_exceeded"] += 1

                logger.warning(
                    "SSE用户并发限制 user_id=%s user_type=%s current=%d max=%d trace_id=%s",
                    user_id, user.user_type, user_connection_count, max_concurrent,
                    get_current_trace_id()
                )
                return False, f"User concurrent SSE limit exceeded ({user_connection_count}/{max_concurrent})", 30

            # 检查对话并发限制（如果指定了conversation_id）
            if conversation_id:
                conv_connection_count = len(self.conversation_connections.get(conversation_id, set()))
                if conv_connection_count >= self.settings.sse_max_concurrent_per_conversation:
                    self.total_connections_rejected += 1
                    self.rejection_reasons["conversation_limit_exceeded"] += 1

                    logger.warning(
                        "SSE对话并发限制 conversation_id=%s current=%d max=%d trace_id=%s",
                        conversation_id, conv_connection_count,
                        self.settings.sse_max_concurrent_per_conversation,
                        get_current_trace_id()
                    )
                    return False, f"Conversation concurrent SSE limit exceeded ({conv_connection_count}/{self.settings.sse_max_concurrent_per_conversation})", 10

            # 注册连接
            connection_info = ConnectionInfo(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                start_time=time.time(),
                client_ip=client_ip,
                user_agent=user_agent
            )

            self.active_connections[connection_id] = connection_info
            self.user_connections[user_id].add(connection_id)
            if conversation_id:
                self.conversation_connections[conversation_id].add(connection_id)

            self.total_connections_created += 1

            logger.info(
                "SSE连接已注册 connection_id=%s user_id=%s conversation_id=%s message_id=%s trace_id=%s",
                connection_id, user_id, conversation_id, message_id, get_current_trace_id()
            )

            return True, "OK", None

    async def unregister_connection(self, connection_id: str) -> None:
        """注销SSE连接。"""
        async with self._lock:
            connection_info = self.active_connections.pop(connection_id, None)
            if not connection_info:
                return

            # 从用户连接集合中移除
            user_connections = self.user_connections.get(connection_info.user_id)
            if user_connections:
                user_connections.discard(connection_id)
                if not user_connections:
                    del self.user_connections[connection_info.user_id]

            # 从对话连接集合中移除
            if connection_info.conversation_id:
                conv_connections = self.conversation_connections.get(connection_info.conversation_id)
                if conv_connections:
                    conv_connections.discard(connection_id)
                    if not conv_connections:
                        del self.conversation_connections[connection_info.conversation_id]

            duration = time.time() - connection_info.start_time
            logger.info(
                "SSE连接已注销 connection_id=%s user_id=%s duration=%.2fs trace_id=%s",
                connection_id, connection_info.user_id, duration, get_current_trace_id()
            )

    async def get_user_connections(self, user_id: str) -> Set[str]:
        """获取用户的活跃连接。"""
        async with self._lock:
            return self.user_connections.get(user_id, set()).copy()

    async def get_conversation_connections(self, conversation_id: str) -> Set[str]:
        """获取对话的活跃连接。"""
        async with self._lock:
            return self.conversation_connections.get(conversation_id, set()).copy()

    async def force_disconnect_user(self, user_id: str) -> int:
        """强制断开用户的所有连接。"""
        async with self._lock:
            connection_ids = self.user_connections.get(user_id, set()).copy()
            for connection_id in connection_ids:
                await self.unregister_connection(connection_id)

            logger.warning(
                "强制断开用户连接 user_id=%s count=%d trace_id=%s",
                user_id, len(connection_ids), get_current_trace_id()
            )
            return len(connection_ids)

    async def get_stats(self) -> Dict:
        """获取统计信息。"""
        async with self._lock:
            return {
                "active_connections": len(self.active_connections),
                "active_users": len(self.user_connections),
                "active_conversations": len(self.conversation_connections),
                "total_created": self.total_connections_created,
                "total_rejected": self.total_connections_rejected,
                "rejection_reasons": dict(self.rejection_reasons),
                "rejection_rate": (
                    self.total_connections_rejected / max(1, self.total_connections_created + self.total_connections_rejected)
                ) * 100
            }

    async def cleanup_stale_connections(self, max_age_seconds: int = 3600) -> int:
        """清理过期连接。"""
        async with self._lock:
            now = time.time()
            stale_connections = []

            for connection_id, info in self.active_connections.items():
                if now - info.start_time > max_age_seconds:
                    stale_connections.append(connection_id)

            for connection_id in stale_connections:
                await self.unregister_connection(connection_id)

            if stale_connections:
                logger.info(
                    "清理过期SSE连接 count=%d max_age=%ds trace_id=%s",
                    len(stale_connections), max_age_seconds, get_current_trace_id()
                )

            return len(stale_connections)


# 全局SSE守卫实例
_sse_guard: Optional[SSEConcurrencyGuard] = None


def get_sse_guard() -> SSEConcurrencyGuard:
    """获取全局SSE守卫实例。"""
    global _sse_guard
    if _sse_guard is None:
        _sse_guard = SSEConcurrencyGuard()
    return _sse_guard


async def check_sse_concurrency(
    connection_id: str,
    user: AuthenticatedUser,
    conversation_id: Optional[str],
    message_id: str,
    request: Request
) -> Optional[JSONResponse]:
    """
    检查SSE并发限制的便捷函数。

    Returns:
        如果被拒绝则返回错误响应，否则返回None
    """
    guard = get_sse_guard()
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    allowed, reason, retry_after = await guard.check_and_register_connection(
        connection_id, user, conversation_id, message_id, client_ip, user_agent
    )

    if not allowed:
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        return create_error_response(
            status_code=429,
            code="SSE_CONCURRENCY_LIMIT_EXCEEDED",
            message=f"SSE concurrency limit exceeded: {reason}",
            headers=headers
        )

    return None


async def unregister_sse_connection(connection_id: str) -> None:
    """注销SSE连接的便捷函数。"""
    guard = get_sse_guard()
    await guard.unregister_connection(connection_id)


def _get_client_ip(request: Request) -> str:
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
