"""对话消息相关路由。"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id, reset_current_request_id, set_current_request_id
from app.core.sse_guard import check_sse_concurrency, unregister_sse_connection
from app.db.sqlite_manager import get_sqlite_manager
from app.services.ai_service import AIMessageInput, AIService, MessageEvent, MessageEventBroker
from app.settings.config import get_settings

router = APIRouter(tags=["messages"])


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Optional[str] = Field(None, min_length=1, description="用户输入的文本（messages 不为空时可省略）")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息")
    skip_prompt: bool = Field(default=False, description="是否跳过后端默认 prompt 注入")

    # OpenAI 兼容透传字段（SSOT：OpenAI 语义）
    model: Optional[str] = Field(None, description="模型名称（OpenAI 语义）")
    messages: Optional[list[dict[str, Any]]] = Field(None, description="OpenAI messages")
    system_prompt: Optional[str] = Field(None, description="system prompt（优先于默认 prompt）")
    tools: Optional[list[Any]] = Field(None, description="OpenAI tools schema 或工具名白名单")
    tool_choice: Any = Field(None, description="OpenAI tool_choice")
    temperature: Optional[float] = Field(None, description="OpenAI temperature")
    top_p: Optional[float] = Field(None, description="OpenAI top_p")
    max_tokens: Optional[int] = Field(None, description="OpenAI max_tokens")

    def _extract_metadata_chat_request(self) -> dict[str, Any]:
        if not isinstance(self.metadata, dict):
            return {}
        raw = self.metadata.get("chat_request")
        if isinstance(raw, dict):
            return raw
        raw = self.metadata.get("openai")
        if isinstance(raw, dict):
            return raw
        return {}

    @model_validator(mode="after")
    def _validate_text_or_messages(self) -> "MessageCreateRequest":
        has_text = bool((self.text or "").strip())
        has_messages = bool(self.messages)
        if not has_text and not has_messages:
            meta_chat = self._extract_metadata_chat_request()
            meta_messages = meta_chat.get("messages") if isinstance(meta_chat, dict) else None
            has_messages = bool(isinstance(meta_messages, list) and len(meta_messages) > 0)
        if not has_text and not has_messages:
            raise ValueError("text_or_messages_required")

        # 透传模式：禁止同时提供 messages(system) 与 system_prompt（避免歧义）。
        if self.skip_prompt:
            system_prompt = (self.system_prompt or "").strip()
            if system_prompt:
                msgs = self.messages
                if not msgs:
                    meta_chat = self._extract_metadata_chat_request()
                    meta_messages = meta_chat.get("messages") if isinstance(meta_chat, dict) else None
                    msgs = meta_messages if isinstance(meta_messages, list) else None
                if isinstance(msgs, list) and any(isinstance(item, dict) and item.get("role") == "system" for item in msgs):
                    raise ValueError("system_prompt_conflict_with_messages_system")
        return self


class MessageCreateResponse(BaseModel):
    message_id: str
    conversation_id: str


@router.post("/messages", response_model=MessageCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_message(
    payload: MessageCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MessageCreateResponse:
    broker: MessageEventBroker = request.app.state.message_broker
    ai_service: AIService = request.app.state.ai_service

    message_id = AIService.new_message_id()

    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    # 兼容：允许 App 把 OpenAI 请求体放在 metadata.chat_request / metadata.openai（简化透传链路）
    meta_chat: dict[str, Any] = {}
    if isinstance(payload.metadata, dict):
        raw = payload.metadata.get("chat_request")
        if isinstance(raw, dict):
            meta_chat = raw
        else:
            raw = payload.metadata.get("openai")
            if isinstance(raw, dict):
                meta_chat = raw

    # SSOT：model 白名单强校验（顶层 model 优先，metadata.model 兜底）
    explicit_model = payload.model.strip() if isinstance(payload.model, str) else ""
    meta_model = ""
    if isinstance(payload.metadata, dict):
        meta_model = str(payload.metadata.get("model") or "").strip()
    if not meta_model and isinstance(meta_chat, dict):
        meta_model = str(meta_chat.get("model") or "").strip()

    if explicit_model and meta_model and explicit_model != meta_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "model_conflict", "message": "model 与 metadata.model 不一致", "request_id": request_id or ""},
        )

    requested_model = explicit_model or meta_model
    if not requested_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "model_required",
                "message": "model 不能为空，请从 /api/v1/llm/models 获取白名单并选择",
                "request_id": request_id or "",
            },
        )

    if not await ai_service.is_model_allowed(requested_model, user_id=current_user.uid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "model_not_allowed",
                "message": "model 不在白名单内（请以 /api/v1/llm/models 返回的 name 为准）",
                "request_id": request_id or "",
            },
        )

    conversation_id = None
    if payload.conversation_id:
        try:
            conversation_id = str(uuid.UUID(str(payload.conversation_id)))
        except Exception:
            conversation_id = None
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    await broker.create_channel(
        message_id,
        owner_user_id=current_user.uid,
        conversation_id=conversation_id,
    )

    # 对齐“顶层字段为 SSOT，metadata.chat_request 仅兜底”的取值顺序
    normalized_messages = payload.messages
    if normalized_messages is None and isinstance(meta_chat, dict):
        meta_messages = meta_chat.get("messages")
        if isinstance(meta_messages, list):
            normalized_messages = [item for item in meta_messages if isinstance(item, dict)]

    normalized_system_prompt = payload.system_prompt
    if not (isinstance(normalized_system_prompt, str) and normalized_system_prompt.strip()) and isinstance(meta_chat, dict):
        meta_system_prompt = meta_chat.get("system_prompt")
        if isinstance(meta_system_prompt, str) and meta_system_prompt.strip():
            normalized_system_prompt = meta_system_prompt.strip()

    normalized_tools = payload.tools
    if normalized_tools is None and isinstance(meta_chat, dict):
        meta_tools = meta_chat.get("tools")
        if isinstance(meta_tools, list):
            normalized_tools = meta_tools

    normalized_tool_choice = payload.tool_choice
    if normalized_tool_choice is None and isinstance(meta_chat, dict):
        normalized_tool_choice = meta_chat.get("tool_choice")

    normalized_temperature = payload.temperature
    if normalized_temperature is None and isinstance(meta_chat, dict):
        t = meta_chat.get("temperature")
        if isinstance(t, (int, float)):
            normalized_temperature = float(t)

    normalized_top_p = payload.top_p
    if normalized_top_p is None and isinstance(meta_chat, dict):
        t = meta_chat.get("top_p")
        if isinstance(t, (int, float)):
            normalized_top_p = float(t)

    normalized_max_tokens = payload.max_tokens
    if normalized_max_tokens is None and isinstance(meta_chat, dict):
        t = meta_chat.get("max_tokens")
        if isinstance(t, int):
            normalized_max_tokens = t

    message_input = AIMessageInput(
        text=payload.text,
        conversation_id=conversation_id,
        metadata=payload.metadata,
        skip_prompt=payload.skip_prompt,
        model=requested_model,
        messages=normalized_messages,
        system_prompt=normalized_system_prompt,
        tools=normalized_tools,
        tool_choice=normalized_tool_choice,
        temperature=normalized_temperature,
        top_p=normalized_top_p,
        max_tokens=normalized_max_tokens,
    )

    async def runner() -> None:
        token = None
        if request_id:
            token = set_current_request_id(request_id)
        try:
            await ai_service.run_conversation(message_id, current_user, message_input, broker)
        finally:
            if token is not None:
                reset_current_request_id(token)

    background_tasks.add_task(runner)
    return MessageCreateResponse(message_id=message_id, conversation_id=conversation_id)


@router.get("/messages/{message_id}/events")
async def stream_message_events(
    message_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    broker: MessageEventBroker = request.app.state.message_broker
    queue = broker.get_channel(message_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")

    conversation_id = request.query_params.get("conversation_id")
    meta = broker.get_meta(message_id)
    if meta is not None:
        # SSOT：message_id 的 owner/conversation 由创建时固化，订阅侧只做校验
        if meta.owner_user_id != current_user.uid:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        if conversation_id and meta.conversation_id and conversation_id != meta.conversation_id:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        conversation_id = meta.conversation_id
    # 并发控制维度：同一用户同一 conversation 只允许 1 条活跃 SSE（message_id 不应绕开该限制）
    concurrency_key = f"{current_user.uid}:{conversation_id or 'no-conversation'}"
    connection_id = concurrency_key

    concurrency_error = await check_sse_concurrency(connection_id, current_user, conversation_id, message_id, request)
    if concurrency_error:
        return concurrency_error

    settings = get_settings()
    heartbeat_interval = max(settings.event_stream_heartbeat_seconds, 0.5)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    async def event_generator():
        started = time.time()
        end_reason = "unknown"
        frames: list[dict[str, Any]] = []
        terminal_sent = False
        try:
            while True:
                if await request.is_disconnected():
                    end_reason = "client_disconnected"
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    heartbeat = json.dumps({"message_id": message_id, "event": "heartbeat"})
                    frames.append({"event": "heartbeat", "data": {"message_id": message_id, "event": "heartbeat"}})
                    yield f"event: heartbeat\ndata: {heartbeat}\n\n"
                    continue

                if item is None:
                    end_reason = "channel_closed"
                    break

                # 脱敏记录 SSE 帧（用于交接/排障，不写入原文内容）
                safe_data = dict(item.data or {})
                if item.event == "content_delta":
                    delta = str(safe_data.get("delta") or "")
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "delta_len": len(delta),
                        "delta_preview": delta[:20],
                    }
                elif item.event == "completed":
                    reply = str(safe_data.get("reply") or "")
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "reply_len": len(reply),
                        "reply_preview": reply[:20],
                    }
                frames.append({"event": item.event, "data": safe_data})

                yield f"event: {item.event}\ndata: {json.dumps(item.data)}\n\n"
                if item.event in {"completed", "error"}:
                    terminal_sent = True
                    end_reason = "terminal_event_sent"
                    break
        finally:
            # SSE 契约：无论任何路径，尽力补发终止事件（error）再关闭连接
            if not terminal_sent:
                fallback = None
                if meta is not None and meta.terminal_event is not None:
                    fallback = meta.terminal_event
                if fallback is None:
                    fallback = MessageEvent(
                        event="error",
                        data={
                            "message_id": message_id,
                            "error": "sse_stream_closed_without_terminal_event",
                            "request_id": request_id,
                        },
                    )
                try:
                    frames.append({"event": fallback.event, "data": {"message_id": message_id, "hint": "terminal_fallback"}})
                    yield f"event: {fallback.event}\ndata: {json.dumps(fallback.data)}\n\n"
                    terminal_sent = True
                    end_reason = f"{end_reason}:terminal_fallback"
                except Exception:
                    pass

            await unregister_sse_connection(connection_id)

            try:
                db = get_sqlite_manager(request.app)
                duration = time.time() - started
                await db.patch_conversation_log_response_payload(
                    message_id,
                    {
                        "sse": {
                            "request_id": request_id,
                            "duration_s": round(duration, 3),
                            "end_reason": end_reason,
                            "frames": frames,
                        }
                    },
                )
            except Exception:
                # 不阻塞 SSE 清理
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
