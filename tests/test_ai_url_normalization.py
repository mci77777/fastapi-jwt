from __future__ import annotations

from app.services.ai_url import build_resolved_endpoints, normalize_ai_base_url


def test_normalize_ai_base_url_strips_common_suffixes():
    assert normalize_ai_base_url("https://api.openai.com/v1") == "https://api.openai.com"
    assert normalize_ai_base_url("https://api.openai.com/v1/") == "https://api.openai.com"
    assert (
        normalize_ai_base_url("https://api.openai.com/v1/chat/completions")
        == "https://api.openai.com"
    )
    assert (
        normalize_ai_base_url("https://api.anthropic.com/v1/messages")
        == "https://api.anthropic.com"
    )


def test_build_resolved_endpoints_perplexity_uses_non_v1_paths():
    resolved = build_resolved_endpoints("https://api.perplexity.ai")
    assert resolved["chat_completions"] == "https://api.perplexity.ai/chat/completions"
    assert resolved["completions"] == "https://api.perplexity.ai/completions"
    assert resolved["models"] == "https://api.perplexity.ai/models"
    assert resolved["embeddings"] == "https://api.perplexity.ai/embeddings"
