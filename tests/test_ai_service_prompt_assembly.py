"""AIService: 组装 System + Tools Prompt，按需注入 tools。"""

from __future__ import annotations

import pytest

from app.auth.provider import UserDetails
from app.services.ai_service import AIMessageInput, AIService


class FakeAIConfigService:
    def __init__(self) -> None:
        self._system = {"id": 1, "content": "SYSTEM_PROMPT", "prompt_type": "system", "tools_json": None, "is_active": True}
        self._tools = {
            "id": 2,
            "content": "TOOLS_PROMPT",
            "prompt_type": "tools",
            "tools_json": [{"type": "function", "function": {"name": "ping", "description": "ping", "parameters": {}}}],
            "is_active": True,
        }

    async def list_prompts(  # noqa: D401
        self,
        *,
        only_active=None,
        prompt_type=None,
        page=1,
        page_size=1,
        **_: object,
    ):
        if only_active and prompt_type == "system":
            return [self._system], 1
        if only_active and prompt_type == "tools":
            return [self._tools], 1
        return [], 0


@pytest.mark.asyncio
async def test_build_openai_request_assembles_prompt_and_injects_tools():
    service = AIService(ai_config_service=FakeAIConfigService())
    # server 默认不执行 tool_calls：只有显式 tool_choice 才会把 active tools 下发给上游
    message = AIMessageInput(messages=[{"role": "user", "content": "hi"}], skip_prompt=False, tool_choice="auto")
    payload = await service._build_openai_request(message, user_details=UserDetails(uid="u1"))

    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "SYSTEM_PROMPT\n\nTOOLS_PROMPT"
    assert payload["tool_choice"] == "auto"
    assert payload["tools"][0]["function"]["name"] == "ping"


@pytest.mark.asyncio
async def test_build_openai_request_does_not_override_explicit_tools_list():
    service = AIService(ai_config_service=FakeAIConfigService())
    message = AIMessageInput(messages=[{"role": "user", "content": "hi"}], skip_prompt=False, tools=[])
    payload = await service._build_openai_request(message, user_details=UserDetails(uid="u1"))

    assert payload["tools"] == []
