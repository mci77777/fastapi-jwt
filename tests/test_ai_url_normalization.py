from __future__ import annotations

from app.services.ai_url import normalize_ai_base_url


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

