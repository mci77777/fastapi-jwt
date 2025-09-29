"""对话消息相关路由。"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.auth import AuthenticatedUser, get_current_user
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker
from app.settings.config import get_settings

router = APIRouter(tags=["messages"])


class MessageCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="用户输入的文本")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息")

    class Config:
        extra = "forbid"


class MessageCreateResponse(BaseModel):
    message_id: str


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

    message_input = AIMessageInput(
        text=payload.text,
        conversation_id=payload.conversation_id,
        metadata=payload.metadata,
    )

    async def runner() -> None:
        await ai_service.run_conversation(message_id, current_user, message_input, broker)

    asyncio.create_task(runner())
    return MessageCreateResponse(message_id=message_id)


@router.get("/messages/{message_id}/events")
async def stream_message_events(
    message_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EventSourceResponse:
    broker: MessageEventBroker = request.app.state.message_broker
    queue = broker.get_channel(message_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")

    settings = get_settings()
    heartbeat_interval = max(settings.event_stream_heartbeat_seconds, 0.5)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                heartbeat = json.dumps({"message_id": message_id, "event": "heartbeat"})
                yield {"event": "heartbeat", "data": heartbeat}
                continue

            if item is None:
                break

            yield {"event": item.event, "data": json.dumps(item.data)}

        await broker.close(message_id)

    return EventSourceResponse(event_generator(), media_type="text/event-stream")
