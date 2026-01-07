from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import ProviderError
from app.services.providers.anthropic_messages import AnthropicMessagesAdapter
from app.services.providers.gemini_generate_content import GeminiGenerateContentAdapter
from app.services.providers.openai_chat_completions import OpenAIChatCompletionsAdapter
from app.services.providers.openai_responses import OpenAIResponsesAdapter


def _make_async_lines(lines: list[str]) -> AsyncIterator[str]:
    async def gen() -> AsyncIterator[str]:
        for line in lines:
            yield line

    return gen()


def _mock_httpx_streaming_sse(
    mock_httpx: MagicMock,
    *,
    lines: list[str],
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> None:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"content-type": "text/event-stream"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aiter_lines = MagicMock(side_effect=lambda: _make_async_lines(lines))
    response.aread = AsyncMock(return_value=b"")

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


@pytest.mark.asyncio
async def test_openai_chat_completions_adapter_parses_content_and_tool_calls_metadata():
    adapter = OpenAIChatCompletionsAdapter()
    published: list[tuple[str, dict[str, Any]]] = []

    async def publish(event: str, data: dict[str, Any]) -> None:
        published.append((event, data))

    lines = [
        'data: {"choices":[{"delta":{"content":"Hello "}}]}',
        "",
        'data: {"choices":[{"delta":{"tool_calls":[{"function":{"name":"gymbro.exercise.search"}}]}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"world"}}]}',
        "",
        'data: {"usage":{"total_tokens":12}}',
        "",
        "data: [DONE]",
        "",
    ]

    with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "upstream-rid"})

        reply_text, response_payload, upstream_request_id, metadata = await adapter.stream(
            endpoint={"base_url": "https://api.openai.com", "timeout": 1},
            api_key="test-api-key",
            openai_req={"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o-mini"},
            timeout=1.0,
            publish=publish,
        )

    assert reply_text == "Hello world"
    assert upstream_request_id == "upstream-rid"
    assert [e for e, _ in published] == ["content_delta", "content_delta"]
    assert "".join(d["delta"] for _, d in published) == "Hello world"
    assert metadata == {"tool_calls": {"names": ["gymbro.exercise.search"]}}
    assert (json.loads(response_payload) or {}).get("usage", {}).get("total_tokens") == 12


@pytest.mark.asyncio
async def test_openai_chat_completions_adapter_supports_multiline_json_and_disconnect():
    adapter = OpenAIChatCompletionsAdapter()
    published: list[tuple[str, dict[str, Any]]] = []

    async def publish(event: str, data: dict[str, Any]) -> None:
        published.append((event, data))

    lines = [
        'data: {"choices":[{"delta":{',
        'data: "content":"Hello"}}]}',
        "",
    ]

    with patch("app.services.providers.openai_chat_completions.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines)

        reply_text, _, _, metadata = await adapter.stream(
            endpoint={"base_url": "https://api.openai.com", "timeout": 1},
            api_key="test-api-key",
            openai_req={"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o-mini"},
            timeout=1.0,
            publish=publish,
        )

    assert reply_text == "Hello"
    assert "".join(d["delta"] for _, d in published) == "Hello"
    assert metadata is None


@pytest.mark.asyncio
async def test_openai_responses_adapter_parses_multiline_delta_and_completed():
    adapter = OpenAIResponsesAdapter()
    published: list[tuple[str, dict[str, Any]]] = []

    async def publish(event: str, data: dict[str, Any]) -> None:
        published.append((event, data))

    lines = [
        'data: {"type":"response.output_text.delta",',
        'data: "delta":"Hi"}',
        "",
        'data: {"type":"response.completed","usage":{"total_tokens":8}}',
        "",
    ]

    with patch("app.services.providers.openai_responses.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"x-request-id": "rid"})

        reply_text, response_payload, upstream_request_id, metadata = await adapter.stream(
            endpoint={"base_url": "https://api.openai.com", "timeout": 1},
            api_key="test-api-key",
            payload={"input": "hi", "model": "gpt-4o-mini"},
            timeout=1.0,
            publish=publish,
        )

    assert reply_text == "Hi"
    assert upstream_request_id == "rid"
    assert metadata is None
    assert [e for e, _ in published] == ["content_delta"]
    assert published[0][1]["delta"] == "Hi"
    assert (json.loads(response_payload) or {}).get("usage", {}).get("total_tokens") == 8


@pytest.mark.asyncio
async def test_anthropic_messages_adapter_parses_text_delta_and_stop():
    adapter = AnthropicMessagesAdapter()
    published: list[tuple[str, dict[str, Any]]] = []

    async def publish(event: str, data: dict[str, Any]) -> None:
        published.append((event, data))

    lines = [
        "event: content_block_delta",
        'data: {"delta":{"type":"text_delta","text":"Hi"}}',
        "",
        "event: message_stop",
        'data: {"usage":{"input_tokens":3,"output_tokens":4}}',
        "",
    ]

    with patch("app.services.providers.anthropic_messages.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines, headers={"request-id": "rid"})

        reply_text, response_payload, upstream_request_id, metadata = await adapter.stream(
            endpoint={"base_url": "https://api.anthropic.com", "timeout": 1},
            api_key="test-api-key",
            payload={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 32, "model": "claude"},
            timeout=1.0,
            publish=publish,
        )

    assert reply_text == "Hi"
    assert upstream_request_id == "rid"
    assert metadata is None
    assert [e for e, _ in published] == ["content_delta"]
    usage = (json.loads(response_payload) or {}).get("usage") or {}
    assert usage.get("input_tokens") == 3
    assert usage.get("output_tokens") == 4


@pytest.mark.asyncio
async def test_anthropic_messages_adapter_error_event_raises_provider_error():
    adapter = AnthropicMessagesAdapter()

    async def publish(_: str, __: dict[str, Any]) -> None:
        return None

    lines = [
        "event: error",
        'data: {"type":"error","message":"boom"}',
        "",
    ]

    with patch("app.services.providers.anthropic_messages.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines)

        with pytest.raises(ProviderError):
            await adapter.stream(
                endpoint={"base_url": "https://api.anthropic.com", "timeout": 1},
                api_key="test-api-key",
                payload={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 32, "model": "claude"},
                timeout=1.0,
                publish=publish,
            )


@pytest.mark.asyncio
async def test_gemini_generate_content_adapter_parses_candidate_text():
    adapter = GeminiGenerateContentAdapter()
    published: list[tuple[str, dict[str, Any]]] = []

    async def publish(event: str, data: dict[str, Any]) -> None:
        published.append((event, data))

    lines = [
        'data: {"candidates":[{"content":{"parts":[{"text":"Hi"}]}}]}',
        "",
        "data: [DONE]",
        "",
    ]

    with patch("app.services.providers.gemini_generate_content.httpx.AsyncClient") as mock_httpx:
        _mock_httpx_streaming_sse(mock_httpx, lines=lines)

        reply_text, _, upstream_request_id, metadata = await adapter.stream(
            endpoint={"base_url": "https://generativelanguage.googleapis.com", "timeout": 1},
            api_key="test-api-key",
            model="gemini-1.5-flash",
            payload={"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
            timeout=1.0,
            publish=publish,
        )

    assert reply_text == "Hi"
    assert upstream_request_id is None
    assert metadata is None
    assert [e for e, _ in published] == ["content_delta"]
    assert published[0][1]["delta"] == "Hi"
