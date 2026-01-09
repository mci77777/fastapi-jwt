import pytest

from app.core.middleware import reset_current_request_id, set_current_request_id
from app.services.ai_service import MessageEvent, MessageEventBroker


@pytest.mark.asyncio
async def test_message_event_broker_enriches_request_id_and_seq():
    broker = MessageEventBroker()
    message_id = "0123456789abcdef0123456789abcdef"
    request_id = "req_demo_001"

    await broker.create_channel(message_id, owner_user_id="user-1", conversation_id="conv-1", request_id=request_id)
    meta = broker.get_meta(message_id)
    assert meta is not None
    assert meta.request_id == request_id

    token = set_current_request_id(request_id)
    try:
        await broker.publish(message_id, MessageEvent(event="content_delta", data={"delta": "Hello"}))
        await broker.publish(
            message_id,
            MessageEvent(
                event="completed",
                data={
                    "reply": "Hello",
                    "reply_len": 5,
                    "provider": "xai",
                    "resolved_model": "grok",
                    "endpoint_id": 123,
                    "upstream_request_id": None,
                    "metadata": None,
                },
            ),
        )
    finally:
        reset_current_request_id(token)

    queue = broker.get_channel(message_id)
    assert queue is not None

    first = await queue.get()
    assert first is not None
    assert first.event == "content_delta"
    assert first.data["message_id"] == message_id
    assert first.data["request_id"] == request_id
    assert first.data["seq"] == 1
    assert first.data["delta"] == "Hello"

    second = await queue.get()
    assert second is not None
    assert second.event == "completed"
    assert second.data["message_id"] == message_id
    assert second.data["request_id"] == request_id
    assert second.data["reply"] == "Hello"
    assert second.data["reply_len"] == 5


@pytest.mark.asyncio
async def test_message_event_broker_enriches_error_event_with_message_and_request_id():
    broker = MessageEventBroker()
    message_id = "0123456789abcdef0123456789abcdef"
    request_id = "req_demo_002"

    await broker.create_channel(message_id, owner_user_id="user-1", conversation_id="conv-1", request_id=request_id)

    token = set_current_request_id(request_id)
    try:
        await broker.publish(message_id, MessageEvent(event="error", data={"code": "provider_error", "message": "boom"}))
    finally:
        reset_current_request_id(token)

    queue = broker.get_channel(message_id)
    assert queue is not None

    item = await queue.get()
    assert item is not None
    assert item.event == "error"
    assert item.data["message_id"] == message_id
    assert item.data["request_id"] == request_id
    assert item.data["code"] == "provider_error"
    assert item.data["message"] == "boom"

