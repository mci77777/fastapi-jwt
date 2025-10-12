"""AI 调用与会话事件管理。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

import anyio
import httpx

from app.auth import (
    AuthenticatedUser,
    ProviderError,
    UserDetails,
    get_auth_provider,
)
from app.auth.provider import AuthProvider
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AIMessageInput:
    text: str
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessageEvent:
    event: str
    data: Dict[str, Any]


class MessageEventBroker:
    """管理消息事件队列，支持 SSE 订阅。"""

    def __init__(self) -> None:
        self._channels: Dict[str, asyncio.Queue[Optional[MessageEvent]]] = {}
        self._lock = asyncio.Lock()

    async def create_channel(self, message_id: str) -> asyncio.Queue[Optional[MessageEvent]]:
        queue: asyncio.Queue[Optional[MessageEvent]] = asyncio.Queue()
        async with self._lock:
            self._channels[message_id] = queue
        return queue

    def get_channel(self, message_id: str) -> Optional[asyncio.Queue[Optional[MessageEvent]]]:
        return self._channels.get(message_id)

    async def publish(self, message_id: str, event: MessageEvent) -> None:
        queue = self._channels.get(message_id)
        if queue:
            await queue.put(event)

    async def close(self, message_id: str) -> None:
        async with self._lock:
            queue = self._channels.pop(message_id, None)
        if queue:
            await queue.put(None)


class AIService:
    """封装 AI 模型调用与聊天记录持久化。"""

    def __init__(
        self,
        provider: Optional[AuthProvider] = None,
        db_manager: Optional[Any] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or get_auth_provider()
        self._db = db_manager  # SQLiteManager 实例（用于记录统计）

    @staticmethod
    def new_message_id() -> str:
        return uuid4().hex

    async def run_conversation(
        self,
        message_id: str,
        user: AuthenticatedUser,
        message: AIMessageInput,
        broker: MessageEventBroker,
    ) -> None:
        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "queued", "message_id": message_id},
            ),
        )

        # 记录 AI 请求统计（Phase 1）
        start_time = perf_counter()
        success = False
        model_used: Optional[str] = None

        try:
            user_details = await anyio.to_thread.run_sync(
                self._provider.get_user_details,
                user.uid,
            )
        except ProviderError as exc:
            logger.error("获取用户信息失败 uid=%s error=%s", user.uid, exc)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={"message_id": message_id, "error": str(exc)},
                ),
            )
            await broker.close(message_id)
            # 记录失败的请求（用户信息获取失败）
            latency_ms = (perf_counter() - start_time) * 1000
            await self._record_ai_request(user.uid, None, None, latency_ms, success=False)
            return

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "working", "message_id": message_id},
            ),
        )

        try:
            reply_text = await self._generate_reply(message, user, user_details)
            # 提取使用的模型名称
            provider = (self._settings.ai_provider or "").lower()
            if provider == "openai":
                model_used = self._settings.ai_model or "gpt-4o-mini"
            else:
                model_used = "default"

            async for chunk in self._stream_chunks(reply_text):
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="content_delta",
                        data={"message_id": message_id, "delta": chunk},
                    ),
                )

            record = {
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "user_id": user.uid,
                "user_message": message.text,
                "ai_reply": reply_text,
                "metadata": message.metadata,
            }
            await anyio.to_thread.run_sync(self._provider.sync_chat_record, record)

            await broker.publish(
                message_id,
                MessageEvent(
                    event="completed",
                    data={"message_id": message_id, "reply": reply_text},
                ),
            )
            success = True
        except Exception as exc:  # pragma: no cover - 运行时防护
            logger.exception("AI 会话处理失败 message_id=%s", message_id)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={"message_id": message_id, "error": str(exc)},
                ),
            )
        finally:
            # 记录 AI 请求统计
            latency_ms = (perf_counter() - start_time) * 1000
            await self._record_ai_request(user.uid, None, model_used, latency_ms, success)
            await broker.close(message_id)

    async def _generate_reply(
        self,
        message: AIMessageInput,
        user: AuthenticatedUser,
        user_details: UserDetails,
    ) -> str:
        if not message.text.strip():
            raise ValueError("Message text can not be empty")

        provider = (self._settings.ai_provider or "").lower()
        if provider == "openai" and self._settings.ai_api_key:
            return await self._call_openai_completion(message, user_details)
        return self._default_reply(message, user_details)

    async def _stream_chunks(self, text: str, chunk_size: int = 120) -> AsyncIterator[str]:
        if not text:
            yield ""
            return
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]
            await asyncio.sleep(0)

    async def _call_openai_completion(
        self,
        message: AIMessageInput,
        user_details: UserDetails,
    ) -> str:
        base_url = (self._settings.ai_api_base_url or "https://api.openai.com/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        payload = {
            "model": self._settings.ai_model or "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are GymBro's AI assistant.",
                },
                {
                    "role": "user",
                    "content": message.text,
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._settings.ai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("AI provider returned empty response")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError("AI provider did not return content")
        return content.strip()

    def _default_reply(self, message: AIMessageInput, user_details: UserDetails) -> str:
        name = user_details.display_name or user_details.email or user_details.uid
        return f"嗨 {name}，我们已收到你的消息：{message.text}"

    async def _record_ai_request(
        self,
        user_id: str,
        endpoint_id: Optional[int],
        model: Optional[str],
        latency_ms: float,
        success: bool,
    ) -> None:
        """记录 AI 请求统计到 ai_request_stats 表。

        Args:
            user_id: 用户 ID
            endpoint_id: 端点 ID（当前为 None，后续可扩展）
            model: 模型名称
            latency_ms: 请求延迟（毫秒）
            success: 是否成功
        """
        if not self._db:
            # 未注入 SQLiteManager，跳过记录
            return

        try:
            today = datetime.now().date().isoformat()

            await self._db.execute(
                """
                INSERT INTO ai_request_stats (
                    user_id, endpoint_id, model, request_date,
                    count, total_latency_ms, success_count, error_count
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(user_id, endpoint_id, model, request_date)
                DO UPDATE SET
                    count = count + 1,
                    total_latency_ms = total_latency_ms + ?,
                    success_count = success_count + ?,
                    error_count = error_count + ?,
                    updated_at = CURRENT_TIMESTAMP
            """,
                [
                    user_id,
                    endpoint_id,
                    model or "unknown",
                    today,
                    latency_ms,
                    1 if success else 0,
                    0 if success else 1,
                    latency_ms,
                    1 if success else 0,
                    0 if success else 1,
                ],
            )
        except Exception as exc:
            # 不阻塞主流程，仅记录日志
            logger.warning("Failed to record AI request stats: %s", exc)
