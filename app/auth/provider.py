"""认证 Provider 抽象层。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UserDetails:
    """统一的用户信息载体。"""

    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Provider 访问或数据同步失败时抛出。"""


class AuthProvider(ABC):
    """统一的认证 Provider 抽象定义。"""

    @abstractmethod
    def get_user_details(self, uid: str) -> UserDetails:
        """根据 UID 获取用户详情。"""

    @abstractmethod
    def sync_chat_record(self, record: Dict[str, Any]) -> None:
        """同步聊天记录，record 格式由业务层约束。"""


class InMemoryProvider(AuthProvider):
    """用于开发与测试的内存 Provider。"""

    def __init__(self) -> None:
        self._users: Dict[str, UserDetails] = {}
        self.records: list[Dict[str, Any]] = []

    def get_user_details(self, uid: str) -> UserDetails:
        return self._users.setdefault(uid, UserDetails(uid=uid))

    def sync_chat_record(self, record: Dict[str, Any]) -> None:
        self.records.append(record)


@lru_cache(maxsize=1)
def get_auth_provider() -> AuthProvider:
    """优先返回 Supabase Provider，不可用时回退到内存实现。"""

    try:
        from .supabase_provider import get_supabase_provider

        return get_supabase_provider()
    except ProviderError as exc:  # pragma: no cover - 配置问题
        logger.warning("Supabase provider unavailable, fallback to InMemoryProvider: %s", exc)
        return InMemoryProvider()
