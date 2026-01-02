"""AI 调用与会话事件管理。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

import httpx
from anyio import to_thread

from app.auth import AuthenticatedUser, ProviderError, UserDetails, get_auth_provider
from app.auth.provider import AuthProvider
from app.core.middleware import REQUEST_ID_HEADER_NAME, get_current_request_id
from app.services.ai_config_service import AIConfigService
from app.services.model_mapping_service import ModelMappingService
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AIMessageInput:
    text: Optional[str] = None
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    skip_prompt: bool = False

    # OpenAI 兼容透传字段（SSOT：OpenAI 语义）
    model: Optional[str] = None
    messages: Optional[list[dict[str, Any]]] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[Any]] = None
    tool_choice: Any = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


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
        queue = self._channels.get(message_id)
        if queue:
            await queue.put(None)


class AIService:
    """封装 AI 模型调用与聊天记录持久化。"""

    def __init__(
        self,
        provider: Optional[AuthProvider] = None,
        db_manager: Optional[Any] = None,
        *,
        ai_config_service: Optional[AIConfigService] = None,
        model_mapping_service: Optional[ModelMappingService] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or get_auth_provider()
        self._db = db_manager  # SQLiteManager 实例（用于记录统计/日志）
        self._ai_config_service = ai_config_service
        self._model_mapping_service = model_mapping_service

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
        request_id = get_current_request_id()

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "queued", "message_id": message_id},
            ),
        )

        start_time = perf_counter()
        success = False
        model_used: Optional[str] = None
        endpoint_id_used: Optional[int] = None
        request_payload: Optional[str] = None
        response_payload: Optional[str] = None
        upstream_request_id: Optional[str] = None
        error_message: Optional[str] = None

        try:
            user_details = await to_thread.run_sync(
                self._provider.get_user_details,
                user.uid,
            )

            await broker.publish(
                message_id,
                MessageEvent(
                    event="status",
                    data={"state": "working", "message_id": message_id},
                ),
            )

            (
                reply_text,
                model_used,
                request_payload,
                response_payload,
                upstream_request_id,
                endpoint_id_used,
            ) = await self._generate_reply(message, user, user_details)

            async for chunk in self._stream_chunks(reply_text):
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="content_delta",
                        data={"message_id": message_id, "delta": chunk},
                    ),
                )

            save_history = bool((message.metadata or {}).get("save_history", True))
            if save_history:
                metadata = dict(message.metadata or {})
                if upstream_request_id:
                    metadata["upstream_request_id"] = upstream_request_id

                record = {
                    "message_id": message_id,
                    "conversation_id": message.conversation_id,
                    "user_id": user.uid,
                    "user_message": message.text or "",
                    "ai_reply": reply_text,
                    "metadata": metadata,
                }
                try:
                    await to_thread.run_sync(self._provider.sync_chat_record, record)
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入对话记录失败 message_id=%s request_id=%s error=%s", message_id, request_id, exc)

            await broker.publish(
                message_id,
                MessageEvent(
                    event="completed",
                    data={"message_id": message_id, "reply": reply_text},
                ),
            )
            success = True
        except ProviderError as exc:  # pragma: no cover - 运行时防护
            error_message = str(exc)[:200]
            logger.error("AI 会话处理失败（provider） message_id=%s request_id=%s error=%s", message_id, request_id, exc)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={"message_id": message_id, "error": str(exc), "request_id": request_id},
                ),
            )
        except Exception as exc:  # pragma: no cover - 运行时防护
            error_message = str(exc)[:200]
            logger.exception("AI 会话处理失败 message_id=%s request_id=%s", message_id, request_id)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={"message_id": message_id, "error": str(exc), "request_id": request_id},
                ),
            )
        finally:
            latency_ms = (perf_counter() - start_time) * 1000
            await self._record_ai_request(user.uid, endpoint_id_used, model_used, latency_ms, success)

            # Prometheus：会话延迟与成功率（按 model/user_type/status 维度）
            try:
                from app.core.metrics import ai_conversation_latency_seconds

                model_label = (
                    model_used
                    or (message.model.strip() if isinstance(message.model, str) and message.model.strip() else None)
                    or (self._settings.ai_model.strip() if isinstance(self._settings.ai_model, str) and self._settings.ai_model.strip() else None)
                    or "unknown"
                )
                ai_conversation_latency_seconds.labels(
                    model=model_label,
                    user_type=user.user_type,
                    status="success" if success else "error",
                ).observe(latency_ms / 1000.0)
            except Exception:  # pragma: no cover
                pass

            if getattr(self._db, "log_conversation", None):
                try:
                    await self._db.log_conversation(
                        user_id=user.uid,
                        message_id=message_id,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        model_used=model_used,
                        latency_ms=latency_ms,
                        status="success" if success else "error",
                        error_message=error_message,
                    )
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入对话日志失败 message_id=%s request_id=%s error=%s", message_id, request_id, exc)

            await broker.close(message_id)

    async def _generate_reply(
        self,
        message: AIMessageInput,
        user: AuthenticatedUser,
        user_details: UserDetails,
    ) -> tuple[str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[int]]:
        if self._ai_config_service is None:
            reply_text = await self._call_openai_completion_settings(message)
            model_used = self._settings.ai_model or "gpt-4o-mini"
            request_payload = json.dumps({"model": model_used, "text": message.text}, ensure_ascii=False)
            return reply_text, model_used, request_payload, None, None, None

        openai_req = await self._build_openai_request(message, user_details=user_details)
        preferred_endpoint_id = _parse_optional_int((message.metadata or {}).get("endpoint_id") or (message.metadata or {}).get("endpointId"))
        selected_endpoint, selected_model, provider_name = await self._select_endpoint_and_model(
            openai_req,
            preferred_endpoint_id=preferred_endpoint_id,
        )

        api_key = await self._get_endpoint_api_key(selected_endpoint)
        if not api_key:
            raise ProviderError("endpoint_missing_api_key")

        request_payload = json.dumps(
            {
                "conversation_id": message.conversation_id,
                "text": message.text,
                "model": openai_req.get("model"),
                "messages": openai_req.get("messages"),
            },
            ensure_ascii=False,
        )

        if provider_name == "claude":
            reply_text, response_payload, upstream_request_id = await self._call_anthropic_messages(
                selected_endpoint,
                api_key,
                openai_req,
            )
            endpoint_id = _parse_optional_int(selected_endpoint.get("id"))
            return reply_text, selected_model, request_payload, response_payload, upstream_request_id, endpoint_id

        reply_text, response_payload, upstream_request_id = await self._call_openai_chat_completions(
            selected_endpoint,
            api_key,
            openai_req,
        )
        endpoint_id = _parse_optional_int(selected_endpoint.get("id"))
        return reply_text, selected_model, request_payload, response_payload, upstream_request_id, endpoint_id

    async def _call_openai_completion_settings(self, message: AIMessageInput) -> str:
        text = (message.text or "").strip()
        if not text:
            raise ValueError("text_or_messages_required")

        api_key = getattr(self._settings, "ai_api_key", None)
        if not api_key:
            raise ProviderError("endpoint_missing_api_key")

        raw_base_url = self._settings.ai_api_base_url or "https://api.openai.com"
        base_url = str(raw_base_url).rstrip("/")
        endpoint = f"{base_url}/v1/chat/completions"

        payload = {
            "model": self._settings.ai_model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are GymBro's AI assistant."},
                {"role": "user", "content": text},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        request_id = get_current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER_NAME] = request_id

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("upstream_empty_choices")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError("upstream_empty_content")
        return content.strip()

    async def _stream_chunks(self, text: str, chunk_size: int = 120) -> AsyncIterator[str]:
        if not text:
            yield ""
            return
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]
            await asyncio.sleep(0)

    async def _build_openai_request(self, message: AIMessageInput, *, user_details: UserDetails) -> dict[str, Any]:
        model = message.model or (message.metadata or {}).get("model") or self._settings.ai_model or "gpt-4o-mini"
        system_prompt = message.system_prompt or (message.metadata or {}).get("system_prompt")
        tools = message.tools if message.tools is not None else (message.metadata or {}).get("tools")

        tool_choice = message.tool_choice
        if tool_choice is None:
            tool_choice = (message.metadata or {}).get("tool_choice")
        if tool_choice is None:
            tool_choice = self._map_legacy_function_call_to_tool_choice((message.metadata or {}).get("function_call"))

        temperature = message.temperature if message.temperature is not None else (message.metadata or {}).get("temperature")
        top_p = message.top_p if message.top_p is not None else (message.metadata or {}).get("top_p")
        max_tokens = message.max_tokens if message.max_tokens is not None else (message.metadata or {}).get("max_tokens")

        messages = message.messages
        if not messages:
            text = (message.text or "").strip()
            if not text:
                raise ValueError("text_or_messages_required")
            messages = [{"role": "user", "content": text}]

        final_messages: list[dict[str, Any]] = []
        explicit_system_prompt = isinstance(system_prompt, str) and bool(system_prompt.strip())
        if explicit_system_prompt:
            final_messages.append({"role": "system", "content": system_prompt.strip()})
            final_messages.extend([item for item in messages if isinstance(item, dict) and item.get("role") != "system"])
        else:
            final_messages.extend(messages)
            if not message.skip_prompt and not any((item or {}).get("role") == "system" for item in messages):
                default_prompt = await self._get_active_prompt_text() or "You are GymBro's AI assistant."
                if default_prompt:
                    final_messages.insert(0, {"role": "system", "content": default_prompt})

        resolved_tools = await self._resolve_tools(tools)
        if resolved_tools is None:
            resolved_tools = await self._get_active_prompt_tools()

        payload: dict[str, Any] = {
            "model": model,
            "messages": final_messages,
        }
        if resolved_tools is not None:
            payload["tools"] = resolved_tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return payload

    def _map_legacy_function_call_to_tool_choice(self, value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("auto", "none", "required"):
                return lowered
            return value
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                return {"type": "function", "function": {"name": name.strip()}}
        return value

    async def _get_active_prompt_text(self) -> Optional[str]:
        if self._ai_config_service is None:
            return None
        try:
            system_prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="system",
                page=1,
                page_size=1,
            )
            tools_prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="tools",
                page=1,
                page_size=1,
            )
        except Exception:
            return None
        parts: list[str] = []
        if system_prompts:
            content = system_prompts[0].get("content")
            if content:
                parts.append(str(content).strip())
        if tools_prompts:
            content = tools_prompts[0].get("content")
            if content:
                parts.append(str(content).strip())
        return "\n\n".join([item for item in parts if item]) if parts else None

    async def _get_active_prompt_tools(self) -> Optional[list[Any]]:
        if self._ai_config_service is None:
            return None
        try:
            prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="tools",
                page=1,
                page_size=1,
            )
        except Exception:
            return None
        if not prompts:
            return None
        tools_json = prompts[0].get("tools_json")
        if isinstance(tools_json, dict):
            raw = tools_json.get("tools")
            if isinstance(raw, list) and raw:
                return raw
            return None
        if isinstance(tools_json, list) and tools_json:
            return tools_json
        return None

    async def _resolve_tools(self, tools_value: Any) -> Optional[list[Any]]:
        if tools_value is None:
            return None
        if isinstance(tools_value, list):
            if not tools_value:
                return []
            if all(isinstance(item, str) for item in tools_value):
                return await self._filter_active_prompt_tools_by_name([str(item) for item in tools_value])
            return tools_value
        return None

    async def _filter_active_prompt_tools_by_name(self, names: list[str]) -> list[Any]:
        wanted = {name.strip() for name in names if name and name.strip()}
        if not wanted or self._ai_config_service is None:
            return []
        prompts, _ = await self._ai_config_service.list_prompts(
            only_active=True,
            prompt_type="tools",
            page=1,
            page_size=1,
        )
        if not prompts:
            return []
        tools_json = prompts[0].get("tools_json")
        candidates: list[Any] = []
        if isinstance(tools_json, dict):
            raw = tools_json.get("tools")
            if isinstance(raw, list):
                candidates = raw
        elif isinstance(tools_json, list):
            candidates = tools_json

        filtered: list[Any] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else None
            name = (function or {}).get("name")
            if isinstance(name, str) and name in wanted:
                filtered.append(item)
        return filtered

    async def _select_endpoint_and_model(
        self,
        openai_req: dict[str, Any],
        *,
        preferred_endpoint_id: Optional[int] = None,
    ) -> tuple[dict[str, Any], Optional[str], str]:
        if self._ai_config_service is None:
            raise ProviderError("ai_config_service_not_initialized")

        raw_model = openai_req.get("model")
        resolved_model = raw_model
        mapping_hit = False
        if isinstance(raw_model, str) and raw_model.strip():
            raw_str = raw_model.strip()
            resolved_model = await self._resolve_mapped_model_name(raw_str)
            if isinstance(resolved_model, str) and resolved_model.strip() and resolved_model.strip() != raw_str:
                mapping_hit = True

        endpoints, _ = await self._ai_config_service.list_endpoints(only_active=True, page=1, page_size=200)
        candidates = [item for item in endpoints if item.get("is_active") and item.get("has_api_key")]
        if not candidates:
            raise ProviderError("no_active_ai_endpoint")

        default_endpoint = next((item for item in candidates if item.get("is_default")), candidates[0])
        selected_endpoint = default_endpoint
        if isinstance(preferred_endpoint_id, int):
            preferred = next(
                (item for item in candidates if _parse_optional_int(item.get("id")) == preferred_endpoint_id),
                None,
            )
            if preferred is None:
                raise ProviderError("endpoint_not_found_or_inactive")
            selected_endpoint = preferred

        if isinstance(resolved_model, str) and resolved_model.strip():
            by_list = next(
                (
                    item
                    for item in candidates
                    if isinstance(item.get("model_list"), list) and resolved_model in (item.get("model_list") or [])
                ),
                None,
            )
            # 仅在未显式指定 endpoint 时，才按 model_list 进行“自动切换端点”。
            if preferred_endpoint_id is None:
                selected_endpoint = by_list or selected_endpoint
            else:
                # 指定 endpoint 时：若该 endpoint 有显式 model_list，则做最小校验（避免误以为生效）。
                # 但当用户传入的是“映射模型 key”时，最终真实模型可能无法通过 /v1/models 枚举到；
                # 此时不应误拦截（仍由上游调用返回错误来兜底）。
                model_list = selected_endpoint.get("model_list")
                if (
                    isinstance(model_list, list)
                    and model_list
                    and resolved_model not in model_list
                    and not mapping_hit
                ):
                    raise ProviderError("model_not_supported_by_endpoint")

        provider_name = self._infer_provider(selected_endpoint)

        # 写回最终 model（SSOT：上游 OpenAI 语义）
        if resolved_model and isinstance(resolved_model, str):
            openai_req["model"] = resolved_model
        else:
            fallback_model = selected_endpoint.get("model")
            if not fallback_model:
                model_list = selected_endpoint.get("model_list") or []
                fallback_model = model_list[0] if model_list else None
            if isinstance(fallback_model, str) and fallback_model.strip():
                openai_req["model"] = await self._resolve_mapped_model_name(fallback_model.strip())

        return selected_endpoint, openai_req.get("model"), provider_name

    async def _resolve_mapped_model_name(self, name: str) -> str:
        if self._model_mapping_service is None:
            return name
        try:
            mappings = await self._model_mapping_service.list_mappings()
        except Exception:
            return name
        for mapping in mappings:
            if not mapping.get("is_active", True):
                continue
            if mapping.get("id") == name or mapping.get("name") == name or mapping.get("scope_key") == name:
                default_model = mapping.get("default_model")
                if isinstance(default_model, str) and default_model.strip():
                    return default_model.strip()
                candidates = mapping.get("candidates") or []
                if isinstance(candidates, list) and candidates and isinstance(candidates[0], str):
                    return candidates[0]
        return name

    def _infer_provider(self, endpoint: dict[str, Any]) -> str:
        base_url = str(endpoint.get("base_url") or "").lower()
        name = str(endpoint.get("name") or "").lower()
        if "anthropic" in base_url or "claude" in name or "anthropic" in name:
            return "claude"
        return "openai"

    async def _get_endpoint_api_key(self, endpoint: dict[str, Any]) -> Optional[str]:
        if self._ai_config_service is None:
            return None
        endpoint_id = endpoint.get("id")
        if endpoint_id is None:
            return None
        try:
            return await self._ai_config_service.get_endpoint_api_key(int(endpoint_id))
        except Exception:
            return None

    async def _call_openai_chat_completions(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        resolved = endpoint.get("resolved_endpoints") or {}
        chat_url = resolved.get("chat_completions") or f"{str(endpoint.get('base_url') or '').rstrip('/')}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        request_id = get_current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER_NAME] = request_id

        # OpenAI 兼容 SSOT：仅转发 OpenAI 语义字段
        payload: dict[str, Any] = {}
        for key in ("model", "messages", "tools", "tool_choice", "temperature", "top_p", "max_tokens"):
            if key in openai_req and openai_req[key] is not None:
                payload[key] = openai_req[key]

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.post(chat_url, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("upstream_empty_choices")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError("upstream_empty_content")

        upstream_request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        return content.strip(), json.dumps(data, ensure_ascii=False), upstream_request_id

    async def _call_anthropic_messages(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        base_url = str(endpoint.get("base_url") or "").rstrip("/")
        messages_url = f"{base_url}/v1/messages"

        anthropic_payload = self._convert_openai_to_anthropic(openai_req)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        request_id = get_current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER_NAME] = request_id

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.post(messages_url, json=anthropic_payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        content_blocks = data.get("content") if isinstance(data, dict) else None
        if not isinstance(content_blocks, list):
            raise ProviderError("upstream_invalid_response")
        text = "".join(block.get("text", "") for block in content_blocks if isinstance(block, dict) and block.get("type") == "text")
        if not text:
            raise ProviderError("upstream_empty_content")

        upstream_request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
        return text.strip(), json.dumps(data, ensure_ascii=False), upstream_request_id

    def _convert_openai_to_anthropic(self, openai_req: dict[str, Any]) -> dict[str, Any]:
        raw_messages = openai_req.get("messages") or []
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append(content.strip())
                continue
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        max_tokens = openai_req.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            max_tokens = 1024

        payload: dict[str, Any] = {
            "model": openai_req.get("model"),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if openai_req.get("temperature") is not None:
            payload["temperature"] = openai_req["temperature"]
        if openai_req.get("top_p") is not None:
            payload["top_p"] = openai_req["top_p"]

        raw_tools = openai_req.get("tools")
        if isinstance(raw_tools, list):
            payload["tools"] = self._map_openai_tools_to_anthropic(raw_tools)

        tool_choice = openai_req.get("tool_choice")
        mapped_tool_choice = self._map_openai_tool_choice_to_anthropic(tool_choice)
        if mapped_tool_choice is not None:
            payload["tool_choice"] = mapped_tool_choice

        return payload

    def _map_openai_tools_to_anthropic(self, tools: list[Any]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") != "function":
                continue
            function = tool.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            mapped.append(
                {
                    "name": name,
                    "description": function.get("description") or "",
                    "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return mapped

    def _map_openai_tool_choice_to_anthropic(self, tool_choice: Any) -> Optional[dict[str, Any]]:
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            lowered = tool_choice.strip().lower()
            if lowered == "auto":
                return {"type": "auto"}
            if lowered == "none":
                return {"type": "none"}
            if lowered == "required":
                return {"type": "any"}
            return None
        if isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                function = tool_choice.get("function")
                if isinstance(function, dict) and isinstance(function.get("name"), str):
                    return {"type": "tool", "name": function["name"]}
            if tool_choice.get("type") in ("auto", "any", "none", "tool"):
                return tool_choice
        return None

    async def _record_ai_request(
        self,
        user_id: str,
        endpoint_id: Optional[int],
        model: Optional[str],
        latency_ms: float,
        success: bool,
    ) -> None:
        """记录 AI 请求统计到 ai_request_stats 表。"""

        if not self._db:
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
            logger.warning("Failed to record AI request stats request_id=%s error=%s", get_current_request_id(), exc)


def _parse_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except Exception:
            return None
    try:
        return int(value)
    except Exception:
        return None
