"""AI 模型规则（SSOT）。"""

from __future__ import annotations


# 说明：
# - 这些模型通常仅用于 embeddings/rerank，不应出现在“App 可选 chat 模型”白名单中。
# - 这是“兜底过滤”，避免供应商 /models 返回混入 embeddings 模型导致映射误选。
_EMBEDDING_MODEL_PREFIXES = (
    "text-embedding-",
    "embedding-",
    "embed-",
    # VoyageAI：模型名通常是 voyage-*，但该供应商是 embeddings 为主（chat 不适用）
    "voyage-",
)

_EMBEDDING_MODEL_KEYWORDS = (
    "embedding",
    "embeddings",
)


def looks_like_embedding_model(model: str) -> bool:
    """判断一个模型名是否大概率为 embeddings-only。"""

    text = str(model or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(_EMBEDDING_MODEL_PREFIXES):
        return True
    return any(keyword in lowered for keyword in _EMBEDDING_MODEL_KEYWORDS)
