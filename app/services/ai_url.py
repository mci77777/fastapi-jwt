"""AI 上游 URL 归一化（SSOT）。"""

from __future__ import annotations

from app.services.url_rewrite import rewrite_localhost_for_docker


_STRIP_SUFFIXES = (
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/models",
    "/v1/embeddings",
    "/v1/messages",
    "/v1",
)


def normalize_ai_base_url(base_url: str) -> str:
    """把用户误填的 base_url 归一化为“上游根地址”。

    典型误配：
    - https://host/v1
    - https://host/v1/chat/completions
    - https://host/v1/models
    - https://host/v1/messages（Anthropic）
    """

    base = str(base_url or "").strip().rstrip("/")
    lowered = base.lower()
    for suffix in _STRIP_SUFFIXES:
        if lowered.endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
            lowered = base.lower()
            break
    return rewrite_localhost_for_docker(base)
