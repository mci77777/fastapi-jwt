"""对话消息相关路由。"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.core.sse_guard import check_sse_concurrency, unregister_sse_connection
from app.db.sqlite_manager import get_sqlite_manager
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker
from app.settings.config import get_settings

router = APIRouter(tags=["messages"])


class MessageCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="用户输入的文本")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息")
    skip_prompt: bool = False

    class Config:
        extra = "forbid"


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
    await broker.create_channel(message_id)

    conversation_id: str
    if payload.conversation_id:
        try:
            conversation_id = str(UUID(payload.conversation_id))
        except (TypeError, ValueError):
            conversation_id = str(uuid4())
    else:
        conversation_id = str(uuid4())
    message_input = AIMessageInput(
        text=payload.text,
        conversation_id=conversation_id,
        raw_conversation_id=payload.conversation_id,
        metadata=payload.metadata,
        skip_prompt=payload.skip_prompt,
    )

    async def runner() -> None:
        await ai_service.run_conversation(message_id, current_user, message_input, broker)

    asyncio.create_task(runner())
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

    # 检查SSE并发限制
    conversation_id = request.query_params.get("conversation_id")
    connection_id = f"{current_user.uid}:{message_id}"

    concurrency_error = await check_sse_concurrency(connection_id, current_user, conversation_id, message_id, request)
    if concurrency_error:
        return concurrency_error

    settings = get_settings()
    heartbeat_interval = max(settings.event_stream_heartbeat_seconds, 0.5)

    async def event_generator():
        started = time.time()
        end_reason = "unknown"
        frames: list[dict[str, Any]] = []
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
                data = dict(item.data or {})
                if item.event == "content_delta":
                    delta = str(data.get("delta") or "")
                    data = {
                        "message_id": data.get("message_id"),
                        "delta_len": len(delta),
                        "delta_preview": delta[:20],
                    }
                elif item.event == "completed":
                    reply = str(data.get("reply") or "")
                    data = {
                        "message_id": data.get("message_id"),
                        "reply_len": len(reply),
                        "reply_preview": reply[:20],
                    }
                frames.append({"event": item.event, "data": data})

                yield f"event: {item.event}\ndata: {json.dumps(item.data)}\n\n"
        finally:
            # 清理连接
            await broker.close(message_id)
            await unregister_sse_connection(connection_id)

            try:
                db = get_sqlite_manager(request.app)
                duration = time.time() - started
                await db.patch_conversation_log_response_payload(
                    message_id,
                    {
                        "sse": {
                            "trace_id": getattr(request.state, "trace_id", None),
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
        },
    )
