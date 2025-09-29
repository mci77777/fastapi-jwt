"""Supabase Provider 实现。"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict

import httpx

from app.settings.config import get_settings

from .provider import AuthProvider, ProviderError, UserDetails

logger = logging.getLogger(__name__)


class SupabaseProvider(AuthProvider):
    """基于 Supabase REST/Admin API 的 Provider 实现。"""

    def __init__(self, project_id: str, service_role_key: str, chat_table: str, timeout: float) -> None:
        if not project_id:
            raise ProviderError("Supabase project id is required")
        if not service_role_key:
            raise ProviderError("Supabase service role key is required")

        self._project_id = project_id
        self._service_role_key = service_role_key
        self._chat_table = chat_table
        self._timeout = timeout
        self._base_url = f"https://{project_id}.supabase.co"

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }

    def get_user_details(self, uid: str) -> UserDetails:
        url = f"{self._base_url}/auth/v1/admin/users/{uid}"
        try:
            response = httpx.get(url, headers=self._headers(), timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - 外部依赖
            logger.error("获取 Supabase 用户失败 uid=%s error=%s", uid, exc)
            raise ProviderError("Failed to fetch user from Supabase") from exc

        data = response.json()
        user = data.get("user", data)
        metadata = user.get("user_metadata") or {}
        return UserDetails(
            uid=user.get("id", uid),
            email=user.get("email"),
            display_name=metadata.get("full_name") or user.get("user_metadata", {}).get("full_name"),
            avatar_url=metadata.get("avatar_url"),
            metadata=metadata,
        )

    def sync_chat_record(self, record: Dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise ProviderError("Chat record must be a dict")

        url = f"{self._base_url}/rest/v1/{self._chat_table}"
        headers = self._headers()
        headers["Prefer"] = "return=minimal"

        try:
            response = httpx.post(url, headers=headers, json=record, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - 外部依赖
            logger.error("同步聊天记录失败: %s", exc)
            raise ProviderError("Failed to sync chat record to Supabase") from exc


@lru_cache(maxsize=1)
def get_supabase_provider() -> SupabaseProvider:
    settings = get_settings()
    project_id = settings.supabase_project_id
    service_key = settings.supabase_service_role_key
    if not project_id or not service_key:
        raise ProviderError(
            "Supabase provider is not configured. Set SUPABASE_PROJECT_ID and SUPABASE_SERVICE_ROLE_KEY env vars.",
        )
    return SupabaseProvider(
        project_id=project_id,
        service_role_key=service_key,
        chat_table=settings.supabase_chat_table,
        timeout=settings.http_timeout_seconds,
    )
