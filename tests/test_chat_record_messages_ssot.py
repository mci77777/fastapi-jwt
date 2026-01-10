from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.auth.jwt_verifier import AuthenticatedUser
from app.auth.provider import InMemoryProvider
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker


class StrictInMemoryProvider(InMemoryProvider):
    def sync_chat_record(self, record):  # type: ignore[override]
        messages = record.get("messages")
        assert isinstance(messages, list) and messages, "record.messages 必须为非空 list（SSOT）"
        super().sync_chat_record(record)


@pytest.mark.asyncio
async def test_run_conversation_persists_messages_list_ssot():
    provider = StrictInMemoryProvider()
    service = AIService(provider=provider)
    service._generate_reply = AsyncMock(
        return_value=(
            "Hi there!",
            "gpt-4o-mini",
            None,
            None,
            None,
            None,
            "openai",
            None,
        )
    )

    user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
    message = AIMessageInput(
        text="Hello",
        conversation_id="00000000-0000-0000-0000-000000000001",
        metadata={"save_history": True},
    )
    broker = MessageEventBroker()

    await service.run_conversation(message_id="msg-123", user=user, message=message, broker=broker)

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.get("conversation_id") == "00000000-0000-0000-0000-000000000001"
    assert record.get("user_id") == "user-123"
    assert record.get("messages")[0] == {"role": "user", "content": "Hello"}
    assert record.get("messages")[-1] == {"role": "assistant", "content": "Hi there!"}
