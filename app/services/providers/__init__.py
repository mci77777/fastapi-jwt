"""Upstream provider adapters (dialect -> request builder + SSE parser)."""

from __future__ import annotations

from app.services.llm_model_registry import LlmDialect

from .anthropic_messages import AnthropicMessagesAdapter
from .gemini_generate_content import GeminiGenerateContentAdapter
from .openai_chat_completions import OpenAIChatCompletionsAdapter
from .openai_responses import OpenAIResponsesAdapter

_OPENAI_CHAT = OpenAIChatCompletionsAdapter()
_OPENAI_RESPONSES = OpenAIResponsesAdapter()
_ANTHROPIC = AnthropicMessagesAdapter()
_GEMINI = GeminiGenerateContentAdapter()


def get_provider_adapter(dialect: LlmDialect):
    if dialect == "openai.chat_completions":
        return _OPENAI_CHAT
    if dialect == "openai.responses":
        return _OPENAI_RESPONSES
    if dialect == "anthropic.messages":
        return _ANTHROPIC
    if dialect == "gemini.generate_content":
        return _GEMINI
    raise ValueError(f"unsupported_dialect:{dialect}")


__all__ = [
    "AnthropicMessagesAdapter",
    "GeminiGenerateContentAdapter",
    "OpenAIChatCompletionsAdapter",
    "OpenAIResponsesAdapter",
    "get_provider_adapter",
]

