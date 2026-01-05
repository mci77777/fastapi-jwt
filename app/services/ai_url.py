"""AI 上游 URL 归一化（SSOT）。"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.services.url_rewrite import rewrite_localhost_for_docker


_STRIP_SUFFIXES = (
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/models",
    "/v1/embeddings",
    "/v1/messages",
    "/v1",
)

DEFAULT_V1_ENDPOINT_PATHS = {
    "chat_completions": "/v1/chat/completions",
    "completions": "/v1/completions",
    "models": "/v1/models",
    "embeddings": "/v1/embeddings",
}

# Perplexity：OpenAI-like，但不使用 /v1 前缀（https://api.perplexity.ai/chat/completions）
PERPLEXITY_ENDPOINT_PATHS = {
    "chat_completions": "/chat/completions",
    "completions": "/completions",
    "models": "/models",
    "embeddings": "/embeddings",
}


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


def _safe_hostname(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        return (urlsplit(text).hostname or "").strip().lower()
    except Exception:
        return ""


def build_resolved_endpoints(base_url: str) -> dict[str, str]:
    """按已知供应商特性生成上游完整 URL（SSOT）。"""

    base = normalize_ai_base_url(base_url)
    host = _safe_hostname(base)

    paths = DEFAULT_V1_ENDPOINT_PATHS
    if host == "api.perplexity.ai":
        paths = PERPLEXITY_ENDPOINT_PATHS

    return {name: f"{base}{path}" if base else path for name, path in paths.items()}
