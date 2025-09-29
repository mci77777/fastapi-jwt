from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.ai import AIPrompt
from app.schemas.llm import ChatMessage, ChatRequest, PromptOverride
from app.services.prompt_builder import prompt_builder


@pytest.mark.asyncio
async def test_prompt_builder_uses_active_prompt(tortoise_setup):
    prompt = await AIPrompt.create(
        name="Default Prompt",
        version="v1",
        system_prompt="You are GymBro",
        tools_json=[{"name": "gymbro.exercise.search"}],
        description="default",
        is_active=True,
        updated_by="seed",
    )

    request = ChatRequest(
        messages=[ChatMessage(role="user", content="hi")],
        user_info={"name": "Tom"},
        extra_context={"plan": "Push"},
    )

    result = await prompt_builder.build(request)

    assert result.prompt.id == prompt.id
    assert any(entry.get("role") == "system" for entry in result.messages)
    assert "[CONTEXT]" in result.system_prompt
    assert "Tom" in result.system_prompt
    assert result.tools == prompt.tools_json


@pytest.mark.asyncio
async def test_prompt_builder_override_tools(tortoise_setup):
    prompt = await AIPrompt.create(
        name="Prompt",
        version="1.0",
        system_prompt="coach",
        tools_json=[{"name": "tool.a"}],
        description=None,
        is_active=True,
        updated_by="seed",
    )

    override = PromptOverride(system_prompt="override", tools_json='[{"name": "tool.b"}]')
    request = ChatRequest(
        messages=[ChatMessage(role="user", content="hello")],
        prompt_id=prompt.id,
        prompt_override=override,
    )

    result = await prompt_builder.build(request)

    assert result.prompt.id == prompt.id
    assert result.system_prompt.startswith("override")
    assert result.tools == [{"name": "tool.b"}]


@pytest.mark.asyncio
async def test_prompt_builder_invalid_tools_json(tortoise_setup):
    prompt = await AIPrompt.create(
        name="Prompt",
        version="1.0",
        system_prompt="coach",
        tools_json=None,
        description=None,
        is_active=True,
        updated_by="seed",
    )

    override = PromptOverride(system_prompt="coach", tools_json="{bad json}")
    request = ChatRequest(
        messages=[ChatMessage(role="user", content="hello")],
        prompt_id=prompt.id,
        prompt_override=override,
    )

    with pytest.raises(HTTPException) as exc:
        await prompt_builder.build(request)

    assert exc.value.status_code == 422
