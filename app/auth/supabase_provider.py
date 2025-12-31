"""Supabase Provider 实现。"""

from __future__ import annotations

import logging
import hashlib
from functools import lru_cache
from typing import Any, Dict
from uuid import UUID

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

        conversation_id = record.get("conversation_id")
        user_id = record.get("user_id")
        user_type = record.get("user_type")
        messages = record.get("messages")

        if not conversation_id or not user_id:
            raise ProviderError("Missing conversation_id or user_id")

        try:
            conversation_uuid = str(UUID(str(conversation_id)))
            user_uuid = str(UUID(str(user_id)))
        except (ValueError, TypeError) as exc:
            raise ProviderError("conversation_id and user_id must be UUID") from exc

        settings = get_settings()
        return_representation = bool(getattr(settings, "supabase_return_representation", False)) and bool(
            getattr(settings, "debug", False)
        )

        headers = self._headers()
        headers["Prefer"] = "return=representation" if return_representation else "return=minimal"

        # 1) Upsert conversations（以 id 为主键）
        try:
            upsert_headers = dict(headers)
            upsert_headers["Prefer"] = (
                "return=representation,resolution=merge-duplicates"
                if return_representation
                else "return=minimal,resolution=merge-duplicates"
            )
            conv_url = f"{self._base_url}/rest/v1/conversations?on_conflict=id"
            conv_payload = {
                "id": conversation_uuid,
                "user_id": user_uuid,
                "title": record.get("title"),
                "is_active": True,
                "user_type": user_type,
            }
            response = httpx.post(conv_url, headers=upsert_headers, json=conv_payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - 外部依赖
            logger.error("同步 conversations 失败: %s", exc)
            raise ProviderError("Failed to sync conversation to Supabase") from exc

        # 2) Insert messages（按消息粒度落库）
        if not isinstance(messages, list) or not messages:
            raise ProviderError("Missing messages list")

        rows: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            content = msg.get("content")
            if not role or not content:
                continue
            rows.append(
                {
                    "conversation_id": conversation_uuid,
                    "user_id": user_uuid,
                    "role": role,
                    "content": content,
                    "user_type": user_type,
                }
            )

        if not rows:
            raise ProviderError("No valid message rows to insert")

        try:
            msg_url = f"{self._base_url}/rest/v1/messages"
            response = httpx.post(msg_url, headers=headers, json=rows, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - 外部依赖
            logger.error("同步 messages 失败: %s", exc)
            raise ProviderError("Failed to sync messages to Supabase") from exc

        # 交接/排障：把“写入摘要”回填到 record（避免改接口签名）
        try:
            summary: Dict[str, Any] = {
                "conversations": {"id": conversation_uuid, "upserted": True},
                "messages": {"inserted": len(rows)},
            }
            if return_representation:
                inserted_rows = response.json()
                if isinstance(inserted_rows, list):
                    ids: list[Any] = []
                    assistant_preview = None
                    assistant_len = None
                    assistant_sha = None
                    for item in inserted_rows:
                        if not isinstance(item, dict):
                            continue
                        if "id" in item:
                            ids.append(item.get("id"))
                        role = item.get("role")
                        content = item.get("content")
                        if role == "assistant" and isinstance(content, str):
                            assistant_len = len(content)
                            assistant_preview = content[:20]
                            assistant_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
                    summary["messages"]["ids"] = ids
                    if assistant_len is not None:
                        summary["messages"]["assistant_content_len"] = assistant_len
                        summary["messages"]["assistant_preview"] = assistant_preview
                        summary["messages"]["assistant_sha256"] = assistant_sha
            record["_sync_result"] = summary
        except Exception:
            record["_sync_result"] = {
                "conversations": {"id": conversation_uuid, "upserted": True},
                "messages": {"inserted": len(rows)},
            }


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
