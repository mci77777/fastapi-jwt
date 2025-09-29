from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.llm import chat as chat_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.ai import AIPrompt
from app.schemas.llm import ChatMessage
from app.services import llm_client as llm_client_module


@pytest.fixture
async def chat_app(tortoise_setup):
    app = FastAPI()
    app.include_router(chat_router.router)

    await User.all().delete()
    await AIPrompt.all().delete()

    user = await User.create(
        username="tester",
        email="tester@example.com",
        password="secret",
        is_active=True,
        is_superuser=True,
    )

    async def _current_user():
        return user

    app.dependency_overrides[AuthControl.is_authed] = _current_user
    return app, user


@pytest.mark.asyncio
async def test_chat_success(monkeypatch, chat_app):
    app, _ = chat_app
    prompt = await AIPrompt.create(
        name="GymBro",
        version="gpt-test",
        system_prompt="You are a coach",
        tools_json=[{"name": "gymbro.exercise.search"}],
        description="",
        is_active=True,
        updated_by="seed",
    )

    class FakeLLMClient:
        async def chat_completion(self, payload, request):
            assert payload["model"] in {prompt.version, prompt.name}
            return {
                "model": "override-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
                "__latency_ms": 42,
            }

    monkeypatch.setattr(llm_client_module, "llm_client", FakeLLMClient())

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["reply"] == "hello"
    assert payload["latency_ms"] == 42
    assert payload["prompt_id"] == prompt.id


@pytest.mark.asyncio
async def test_chat_invalid_tools(monkeypatch, chat_app):
    app, _ = chat_app
    await AIPrompt.create(
        name="GymBro",
        version="gpt-test",
        system_prompt="You are a coach",
        tools_json=None,
        description="",
        is_active=True,
        updated_by="seed",
    )

    class FakeLLMClient:
        async def chat_completion(self, payload, request):
            raise AssertionError("chat_completion should not be called on invalid toolsJson")

    monkeypatch.setattr(llm_client_module, "llm_client", FakeLLMClient())

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "promptOverride": {"toolsJson": "{bad json}"},
            },
        )

    assert response.status_code == 422
