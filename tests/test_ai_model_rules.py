from __future__ import annotations

from app.services.ai_model_rules import looks_like_embedding_model


def test_looks_like_embedding_model_detects_common_patterns() -> None:
    assert looks_like_embedding_model("text-embedding-3-large") is True
    assert looks_like_embedding_model("Qwen3-Embedding-8B") is True
    assert looks_like_embedding_model("voyage-3") is True
    assert looks_like_embedding_model("gpt-4o-mini") is False
