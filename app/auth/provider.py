"""认证 Provider 抽象层。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
