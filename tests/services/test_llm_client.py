from __future__ import annotations

import pytest
import respx
from fastapi import HTTPException
from httpx import Response

from app.models.ai import AIModel
from app.schemas.llm import ChatMessage, ChatRequest, LLMOverrideConfig
from app.services.llm_client import llm_client
from app.settings import settings


@pytest.mark.asyncio
@respx.mock
async def test_llm_client_respects_override(monkeypatch, tortoise_setup):
    settings.OPENAI_API_BASE_URL = "https://default-llm.example/v1/chat"
    settings.OPENAI_API_MODEL = "default-model"
    settings.OPENAI_TIMEOUT_SECONDS = 30

    route = respx.post("https://override-llm.example/v1/chat").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hello"}, "index": 0}]},
        )
    )

    request = ChatRequest(
        messages=[ChatMessage(role="user", content="hi")],
        override_config=LLMOverrideConfig(
            base_url="https://override-llm.example/v1/chat",
            api_key="secret",
            model="override-model",
            timeout=10,
        ),
    )

    data = await llm_client.chat_completion({}, request)

    assert route.called
    assert data["choices"][0]["message"]["content"] == "hello"
    assert data["__latency_ms"] >= 0


@pytest.mark.asyncio
@respx.mock
async def test_llm_client_uses_database_model(monkeypatch, tortoise_setup):
    settings.OPENAI_API_BASE_URL = "https://default-llm.example/v1/chat"
    settings.OPENAI_API_MODEL = "fallback-model"
    settings.OPENAI_TIMEOUT_SECONDS = 30

    await AIModel.create(
        name="gymbro-override",
        model="gymbro-override",
        base_url="https://db-llm.example/v1/chat",
        api_key="db-key",
        description="",
        timeout=20,
        is_active=True,
        is_default=True,
    )

    route = respx.post("https://db-llm.example/v1/chat").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hey"}, "index": 0}]},
        )
    )

    request = ChatRequest(messages=[ChatMessage(role="user", content="hello")])

    data = await llm_client.chat_completion({}, request)

    assert route.called
    assert data["choices"][0]["message"]["content"] == "hey"


@pytest.mark.asyncio
async def test_llm_client_missing_base_url(tortoise_setup):
    settings.OPENAI_API_BASE_URL = ""
    settings.OPENAI_API_MODEL = "model-a"
    settings.OPENAI_TIMEOUT_SECONDS = 30

    await AIModel.all().delete()

    request = ChatRequest(messages=[ChatMessage(role="user", content="hi")])

    with pytest.raises(HTTPException) as exc:
        await llm_client.chat_completion({}, request)

    assert exc.value.status_code == 400
    assert "base_url" in exc.value.detail
