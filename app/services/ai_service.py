"""AI 调用与会话事件管理。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

import httpx
from anyio import to_thread

from app.auth import AuthenticatedUser, ProviderError, UserDetails, get_auth_provider
from app.auth.provider import AuthProvider
from app.core.middleware import get_current_trace_id
from app.services.ai_config_service import AIConfigService
from app.services.model_mapping_service import ModelMappingService
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AIMessageInput:
    text: str
    conversation_id: Optional[str] = None
    raw_conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    skip_prompt: bool = False


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
        ai_config_service: Optional[AIConfigService] = None,
        model_mapping_service: Optional[ModelMappingService] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or get_auth_provider()
        self._db = db_manager  # SQLiteManager 实例（用于记录统计）
        self._ai_config = ai_config_service
        self._mappings = model_mapping_service

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
        trace_id = get_current_trace_id()
        request_received_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        sse_event_sources = {
            "status": "AIService.run_conversation",
            "content_delta": "AIService.run_conversation",
            "completed": "AIService.run_conversation",
            "error": "AIService.run_conversation",
        }

        def _sha256_prefix(text: str, n: int = 12) -> str:
            if not text:
                return ""
            return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]

        broker_events: list[dict[str, Any]] = []

        def _record_event(event: str, data: dict[str, Any]) -> None:
            safe_data: dict[str, Any] = dict(data or {})
            if event == "content_delta":
                delta = str(safe_data.get("delta") or "")
                safe_data = {
                    "message_id": safe_data.get("message_id"),
                    "delta_len": len(delta),
                    "delta_preview": delta[:20],
                    "delta_sha256": _sha256_prefix(delta),
                }
            elif event == "completed":
                reply = str(safe_data.get("reply") or "")
                safe_data = {
                    "message_id": safe_data.get("message_id"),
                    "reply_len": len(reply),
                    "reply_preview": reply[:20],
                    "reply_sha256": _sha256_prefix(reply),
                }
            broker_events.append(
                {
                    "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "event": event,
                    "data": safe_data,
                }
            )

        request_payload = {
            "trace_id": trace_id,
            "message_id": message_id,
            "user_id": user.uid,
            "conversation_id": message.conversation_id,
            "request_received_at": request_received_at,
            "request_parsed": {
                "text_len": len(message.text or ""),
                "conversation_id_raw": message.raw_conversation_id,
                "conversation_id_raw_empty": message.raw_conversation_id == "",
                "conversation_id_normalized": message.conversation_id,
                "metadata_type": type(message.metadata).__name__,
                "metadata_keys_count": len(message.metadata) if isinstance(message.metadata, dict) else None,
                "skip_prompt": bool(message.skip_prompt),
                "additional_properties_policy": "forbid",
                "additional_properties_violation": False,
            },
        }

        selection_payload: dict[str, Any] = {
            "provider": None,
            "endpoint_id": None,
            "model": None,
            "prompt": {"prompt_id": None, "name": None, "version": None},
            "temperature": None,
            "mapping": {"hit": None, "chain": [], "reason": None},
        }

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "queued", "message_id": message_id},
            ),
        )
        _record_event("status", {"state": "queued", "message_id": message_id})

        # 记录 AI 请求统计（Phase 1）
        start_time = perf_counter()
        success = False
        model_used: Optional[str] = None
        reply_text: str = ""
        llm_meta: dict[str, Any] = {
            "called": False,
            "reason_code": "not_started",
            "reason_detail": None,
            "request_id": None,
            "started_at": None,
            "ended_at": None,
            "duration_ms": None,
            "upstream_status": None,
            "upstream_error": None,
            "usage": None,
        }
        supabase_summary: Optional[dict[str, Any]] = None
        error_message: Optional[str] = None

        try:
            user_details = await to_thread.run_sync(
                self._provider.get_user_details,
                user.uid,
            )
        except ProviderError as exc:
            error_message = str(exc)
            logger.error("获取用户信息失败 uid=%s error=%s", user.uid, exc)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={"message_id": message_id, "error": str(exc)},
                ),
            )
            _record_event("error", {"message_id": message_id, "error": str(exc)})
            await broker.close(message_id)
            # 记录失败的请求（用户信息获取失败）
            latency_ms = (perf_counter() - start_time) * 1000
            await self._record_ai_request(user.uid, None, None, latency_ms, success=False)

            if self._db and hasattr(self._db, "log_conversation"):
                response_payload = {
                    "trace_id": trace_id,
                    "message_id": message_id,
                    "status": "error",
                    "selection": selection_payload,
                    "llm_called": False,
                    "llm": {**llm_meta, "called": False, "reason_code": "auth_provider_user_lookup_failed"},
                    "error": {"code": "provider_error", "message": error_message},
                    "broker_events": broker_events,
                    "sse_event_sources": sse_event_sources,
                }
                await self._db.log_conversation(
                    user_id=user.uid,
                    message_id=message_id,
                    request_payload=json.dumps(request_payload, ensure_ascii=False),
                    response_payload=json.dumps(response_payload, ensure_ascii=False),
                    model_used=None,
                    latency_ms=latency_ms,
                    status="error",
                    error_message=error_message,
                )
            return

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "working", "message_id": message_id},
            ),
        )
        _record_event("status", {"state": "working", "message_id": message_id})

        try:
            reply_text, llm_meta, selection_payload = await self._generate_reply_with_meta(message, user, user_details)
            model_used = selection_payload.get("model") if isinstance(selection_payload, dict) else None

            if not reply_text:
                reason = llm_meta.get("reason_code") if isinstance(llm_meta, dict) else "unknown"
                error_message = str(llm_meta.get("reason_detail") or reason)
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="error",
                        data={"message_id": message_id, "error": error_message, "reason": reason},
                    ),
                )
                _record_event("error", {"message_id": message_id, "error": error_message})
                return

            async for chunk in self._stream_chunks(reply_text):
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="content_delta",
                        data={"message_id": message_id, "delta": chunk},
                    ),
                )
                _record_event("content_delta", {"message_id": message_id, "delta": chunk})

            record = {
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "user_id": user.uid,
                "metadata": message.metadata,
                "user_type": user.user_type,
                "title": (message.text or "").strip()[:80] or None,
                "messages": [
                    {"role": "user", "content": message.text, "metadata": message.metadata},
                    {"role": "assistant", "content": reply_text, "metadata": {}},
                ],
            }
            await to_thread.run_sync(self._provider.sync_chat_record, record)
            if isinstance(record.get("_sync_result"), dict):
                supabase_summary = record.get("_sync_result")

            await broker.publish(
                message_id,
                MessageEvent(
                    event="completed",
                    data={"message_id": message_id, "reply": reply_text},
                ),
            )
            _record_event("completed", {"message_id": message_id, "reply": reply_text})
            success = True
        except Exception as exc:  # pragma: no cover - 运行时防护
            error_message = str(exc)
            logger.exception("AI 会话处理失败 message_id=%s", message_id)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={
                        "message_id": message_id,
                        "error": str(exc),
                        "reason": llm_meta.get("reason_code") if isinstance(llm_meta, dict) else None,
                    },
                ),
            )
            _record_event("error", {"message_id": message_id, "error": error_message})
        finally:
            # 记录 AI 请求统计
            latency_ms = (perf_counter() - start_time) * 1000
            endpoint_id = selection_payload.get("endpoint_id") if isinstance(selection_payload, dict) else None
            await self._record_ai_request(user.uid, endpoint_id, model_used, latency_ms, success)

            if self._db and hasattr(self._db, "log_conversation"):
                try:
                    completed_sha = _sha256_prefix(reply_text or "")
                    supabase_sha = None
                    if isinstance(supabase_summary, dict):
                        msgs = supabase_summary.get("messages")
                        if isinstance(msgs, dict):
                            supabase_sha = msgs.get("assistant_sha256")
                    response_payload = {
                        "trace_id": trace_id,
                        "message_id": message_id,
                        "conversation_id": message.conversation_id,
                        "user_id": user.uid,
                        "user_type": user.user_type,
                        "status": "success" if success else "error",
                        "selection": selection_payload,
                        "llm_called": bool(llm_meta.get("called")) if isinstance(llm_meta, dict) else False,
                        "llm": llm_meta,
                        "broker_events": broker_events,
                        "completed": (
                            {
                                "reply_len": len(reply_text or ""),
                                "reply_preview": (reply_text or "")[:20],
                                "reply_sha256": completed_sha,
                                "source": sse_event_sources["completed"],
                            }
                            if success
                            else None
                        ),
                        "supabase": supabase_summary,
                        "sse_event_sources": sse_event_sources,
                        "ssot": {
                            "assistant_reply_matches_completed": (
                                True if not supabase_sha else str(supabase_sha) == str(completed_sha)
                            ),
                        },
                    }
                    if error_message:
                        response_payload["error"] = {
                            "message": error_message,
                            "source": sse_event_sources["error"],
                            "reason_code": llm_meta.get("reason_code") if isinstance(llm_meta, dict) else None,
                        }
                    await self._db.log_conversation(
                        user_id=user.uid,
                        message_id=message_id,
                        request_payload=json.dumps(request_payload, ensure_ascii=False),
                        response_payload=json.dumps(response_payload, ensure_ascii=False),
                        model_used=model_used,
                        latency_ms=latency_ms,
                        status="success" if success else "error",
                        error_message=error_message,
                    )
                except Exception as log_exc:  # pragma: no cover - 不阻塞主流程
                    logger.warning("Failed to write conversation_logs: %s", log_exc)
            await broker.close(message_id)

    async def _generate_reply_with_meta(
        self,
        message: AIMessageInput,
        user: AuthenticatedUser,
        user_details: UserDetails,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        if not message.text.strip():
            raise ValueError("Message text can not be empty")

        if self._ai_config is None or self._mappings is None:
            return (
                "",
                {
                    "called": False,
                    "reason_code": "ai_config_not_initialised",
                    "reason_detail": "AI config services not initialised",
                    "request_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "duration_ms": None,
                    "upstream_status": None,
                    "upstream_error": None,
                    "usage": None,
                },
                {
                    "provider": None,
                    "endpoint_id": None,
                    "model": None,
                    "prompt": {"prompt_id": None, "name": None, "version": None},
                    "temperature": None,
                    "mapping": {"hit": None, "chain": [], "reason": "ai_config_not_initialised"},
                },
            )

        prompt = None
        prompt_id = None
        prompt_name = None
        prompt_version = None
        if not message.skip_prompt:
            prompts, _ = await self._ai_config.list_prompts(only_active=True, page=1, page_size=1)
            if prompts:
                prompt = prompts[0]
                prompt_id = prompt.get("id")
                prompt_name = prompt.get("name")
                prompt_version = prompt.get("version")

        tenant_id = None
        if isinstance(message.metadata, dict):
            tenant_id = message.metadata.get("tenant_id") or message.metadata.get("tenant")

        mapping_result = await self._mappings.resolve_for_message(
            user_id=user.uid,
            tenant_id=str(tenant_id) if tenant_id else None,
            prompt_id=int(prompt_id) if prompt_id is not None else None,
        )

        model = mapping_result.get("model")
        temperature = mapping_result.get("temperature")

        selection_payload: dict[str, Any] = {
            "provider": None,
            "endpoint_id": None,
            "model": model,
            "prompt": {"prompt_id": prompt_id, "name": prompt_name, "version": prompt_version},
            "temperature": temperature,
            "mapping": {
                "hit": mapping_result.get("hit"),
                "chain": mapping_result.get("chain") or [],
                "reason": mapping_result.get("reason"),
            },
            "model_source": "mapping",
        }

        if not isinstance(model, str) or not model.strip():
            # SSOT fallback：若 mapping 未命中，则尝试使用“默认 endpoint 的配置 model / model_list”作为模型来源
            endpoints, _ = await self._ai_config.list_endpoints(only_active=True, page=1, page_size=100)
            candidates = [ep for ep in endpoints if ep.get("has_api_key")]
            candidates.sort(key=lambda ep: (not bool(ep.get("is_default")), -(ep.get("id") or 0)))
            default_ep = candidates[0] if candidates else None

            fallback_model = None
            if isinstance(default_ep, dict):
                configured_model = default_ep.get("model")
                if isinstance(configured_model, str) and configured_model.strip():
                    fallback_model = configured_model.strip()
                else:
                    model_list = default_ep.get("model_list") or []
                    if isinstance(model_list, list) and model_list:
                        fallback_model = str(model_list[0])

            if isinstance(fallback_model, str) and fallback_model.strip():
                selection_payload["model"] = fallback_model.strip()
                selection_payload["model_source"] = "endpoint_default"
                selection_payload["mapping"]["fallback_used"] = True
                selection_payload["mapping"]["fallback_reason"] = mapping_result.get("reason")
                model = fallback_model.strip()
            else:
                reason_code = str(mapping_result.get("reason") or "model_selection_empty")
                return (
                    "",
                    {
                        "called": False,
                        "reason_code": reason_code,
                        "reason_detail": "model_selection_empty",
                        "request_id": None,
                        "started_at": None,
                        "ended_at": None,
                        "duration_ms": None,
                        "upstream_status": None,
                        "upstream_error": None,
                        "usage": None,
                    },
                    selection_payload,
                )

        endpoint, endpoint_reason = await self._select_endpoint_for_model(model.strip())
        if endpoint is None:
            reason_code = f"endpoint_selection_failed:{endpoint_reason}"
            return (
                "",
                {
                    "called": False,
                    "reason_code": reason_code,
                    "reason_detail": endpoint_reason,
                    "request_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "duration_ms": None,
                    "upstream_status": None,
                    "upstream_error": None,
                    "usage": None,
                },
                selection_payload,
            )

        selection_payload["endpoint_id"] = endpoint.get("id")
        selection_payload["provider"] = self._infer_provider_name(endpoint)

        api_key = await self._ai_config.get_endpoint_api_key(int(endpoint["id"]))
        if not api_key:
            return (
                "",
                {
                    "called": False,
                    "reason_code": "endpoint_api_key_missing",
                    "reason_detail": "endpoint_api_key_missing",
                    "request_id": None,
                    "started_at": None,
                    "ended_at": None,
                    "duration_ms": None,
                    "upstream_status": None,
                    "upstream_error": None,
                    "usage": None,
                },
                selection_payload,
            )

        system_prompt = None
        if prompt and isinstance(prompt.get("content"), str) and not message.skip_prompt:
            system_prompt = prompt.get("content")

        reply, llm_meta = await self._call_chat_completions_with_meta(
            endpoint=endpoint,
            api_key=api_key,
            model=model.strip(),
            user_text=message.text,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        if not reply:
            # 上游失败：不允许走回显，直接 error（由调用方发送 event:error）
            return "", llm_meta, selection_payload

        return reply, llm_meta, selection_payload

    async def _stream_chunks(self, text: str, chunk_size: int = 120) -> AsyncIterator[str]:
        if not text:
            yield ""
            return
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]
            await asyncio.sleep(0)

    async def _select_endpoint_for_model(self, model: str) -> tuple[dict[str, Any] | None, str | None]:
        if self._ai_config is None:
            return None, "ai_config_not_initialised"
        endpoints, _ = await self._ai_config.list_endpoints(only_active=True, page=1, page_size=100)
        if not endpoints:
            return None, "no_active_endpoint"

        def _supports(ep: dict[str, Any]) -> bool:
            model_list = ep.get("model_list") or []
            if isinstance(model_list, list) and model_list:
                return model in model_list
            configured_model = ep.get("model")
            if isinstance(configured_model, str) and configured_model.strip():
                return configured_model.strip() == model
            return True

        candidates = [ep for ep in endpoints if ep.get("has_api_key") and _supports(ep)]
        if not candidates:
            with_key = [ep for ep in endpoints if ep.get("has_api_key")]
            if not with_key:
                return None, "endpoint_missing_api_key"
            return None, "model_not_activated"

        candidates.sort(key=lambda ep: (not bool(ep.get("is_default")), -(ep.get("id") or 0)))
        return candidates[0], None

    def _infer_provider_name(self, endpoint: dict[str, Any]) -> str:
        base_url = str(endpoint.get("base_url") or "").lower()
        name = str(endpoint.get("name") or "").lower()
        if "openai" in base_url or "openai" in name:
            return "openai"
        if "azure" in base_url or "azure" in name:
            return "azure_openai"
        return "openai_compat"

    async def _call_chat_completions_with_meta(
        self,
        *,
        endpoint: dict[str, Any],
        api_key: str,
        model: str,
        user_text: str,
        system_prompt: str | None,
        temperature: float | None,
    ) -> tuple[str, dict[str, Any]]:
        resolved = endpoint.get("resolved_endpoints") if isinstance(endpoint.get("resolved_endpoints"), dict) else {}
        url = resolved.get("chat_completions") or (str(endpoint.get("base_url") or "").rstrip("/") + "/v1/chat/completions")

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_text})

        payload: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        timeout = float(endpoint.get("timeout") or self._settings.http_timeout_seconds)

        started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        call_start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            ended_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            duration_ms = (perf_counter() - call_start) * 1000
            return (
                "",
                {
                    "called": True,
                    "reason_code": "upstream_timeout",
                    "reason_detail": str(exc),
                    "provider": self._infer_provider_name(endpoint),
                    "endpoint_id": endpoint.get("id"),
                    "request_id": None,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": round(duration_ms, 2),
                    "upstream_status": None,
                    "upstream_error": "timeout",
                    "usage": None,
                },
            )
        except httpx.HTTPStatusError as exc:
            ended_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            duration_ms = (perf_counter() - call_start) * 1000
            status_code = exc.response.status_code
            request_id = exc.response.headers.get("x-request-id") or exc.response.headers.get("x-request_id")
            return (
                "",
                {
                    "called": True,
                    "reason_code": f"upstream_http_{status_code}",
                    "reason_detail": f"http_{status_code}",
                    "provider": self._infer_provider_name(endpoint),
                    "endpoint_id": endpoint.get("id"),
                    "request_id": request_id,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": round(duration_ms, 2),
                    "upstream_status": status_code,
                    "upstream_error": "http_status",
                    "usage": None,
                },
            )
        except httpx.RequestError as exc:
            ended_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            duration_ms = (perf_counter() - call_start) * 1000
            return (
                "",
                {
                    "called": True,
                    "reason_code": "upstream_network_error",
                    "reason_detail": str(exc),
                    "provider": self._infer_provider_name(endpoint),
                    "endpoint_id": endpoint.get("id"),
                    "request_id": None,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": round(duration_ms, 2),
                    "upstream_status": None,
                    "upstream_error": "network_error",
                    "usage": None,
                },
            )

        ended_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        duration_ms = (perf_counter() - call_start) * 1000
        data = response.json()

        choices = data.get("choices") or []
        if not choices:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-request_id")
            return (
                "",
                {
                    "called": True,
                    "reason_code": "upstream_empty_choices",
                    "reason_detail": "empty_choices",
                    "provider": self._infer_provider_name(endpoint),
                    "endpoint_id": endpoint.get("id"),
                    "request_id": request_id,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": round(duration_ms, 2),
                    "upstream_status": response.status_code,
                    "upstream_error": "empty_choices",
                    "usage": None,
                },
            )

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-request_id")
            return (
                "",
                {
                    "called": True,
                    "reason_code": "upstream_empty_content",
                    "reason_detail": "empty_content",
                    "provider": self._infer_provider_name(endpoint),
                    "endpoint_id": endpoint.get("id"),
                    "request_id": request_id,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": round(duration_ms, 2),
                    "upstream_status": response.status_code,
                    "upstream_error": "empty_content",
                    "usage": None,
                },
            )

        usage = data.get("usage") if isinstance(data, dict) else None
        request_id = response.headers.get("x-request-id") or response.headers.get("x-request_id")
        meta = {
            "called": True,
            "reason_code": None,
            "reason_detail": None,
            "provider": self._infer_provider_name(endpoint),
            "endpoint_id": endpoint.get("id"),
            "request_id": request_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": round(duration_ms, 2),
            "upstream_status": response.status_code,
            "upstream_error": None,
            "usage": usage if isinstance(usage, dict) else None,
            "reply_chars": len(content.strip()),
        }
        return content.strip(), meta

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
