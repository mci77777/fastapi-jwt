"""Web 搜索服务（默认：Exa）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class WebSearchError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _compact_text(value: str, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if max_len > 0 and len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    title: str
    url: str
    published_date: Optional[str] = None
    author: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None


@dataclass(frozen=True, slots=True)
class WebSearchResponse:
    provider: str
    request_id: Optional[str]
    total: int
    results: list[WebSearchResult]
    cost: Optional[dict[str, Any]] = None


class WebSearchService:
    """Web 搜索服务（SSOT：只在后端执行；返回给客户端的结果已做裁剪）。"""

    def __init__(self, *, timeout_seconds: float = 10.0, cache_ttl_seconds: int = 300) -> None:
        self._timeout_seconds = float(timeout_seconds)
        self._cache_ttl_seconds = int(cache_ttl_seconds)
        # key -> (expires_at_epoch_s, response)
        self._cache: dict[str, tuple[float, WebSearchResponse]] = {}

    def _cache_get(self, key: str) -> Optional[WebSearchResponse]:
        item = self._cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= time.time():
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: WebSearchResponse) -> None:
        ttl = max(self._cache_ttl_seconds, 0)
        if ttl <= 0:
            return
        self._cache[key] = (time.time() + ttl, value)

    async def search_exa(
        self,
        *,
        api_key: str,
        query: str,
        top_k: int = 5,
        snippet_max_len: int = 240,
    ) -> WebSearchResponse:
        """Exa Search API (best-effort).

        Notes:
        - 为控成本与传输体积：只透出 title/url/published_date/snippet（snippet 从 summary/highlights/text 裁剪）。
        - 不透出上游全文 text。
        """

        q = str(query or "").strip()
        if not q:
            raise WebSearchError("query_required", "query is required")
        key = str(api_key or "").strip()
        if not key:
            raise WebSearchError("missing_api_key", "EXA api key is required")

        k = int(top_k)
        if k <= 0:
            k = 5
        if k > 10:
            k = 10

        cache_key = f"exa:{k}:{q.lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = "https://api.exa.ai/search"
        headers = {"Content-Type": "application/json", "x-api-key": key}
        # 兼容 Exa 文档示例：`text: true` 会在结果中返回 text/highlights/summary 等字段。
        body = {"query": q, "numResults": k, "type": "auto", "text": True}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, json=body, headers=headers)
        except Exception as exc:  # pragma: no cover
            raise WebSearchError("network_error", str(exc) or type(exc).__name__) from exc

        if resp.status_code >= 400:
            msg = ""
            try:
                msg = resp.text
            except Exception:
                msg = ""
            raise WebSearchError("upstream_error", f"Exa error status={resp.status_code} body={_compact_text(msg, max_len=200)}")

        try:
            data = resp.json()
        except Exception as exc:
            raise WebSearchError("upstream_invalid_json", "Exa response is not valid JSON") from exc

        raw_results = data.get("results") if isinstance(data, dict) else None
        results: list[WebSearchResult] = []
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                title = _compact_text(str(item.get("title") or ""), max_len=200)
                url_item = str(item.get("url") or "").strip()
                if not url_item:
                    continue
                published_date = str(item.get("publishedDate") or item.get("published_date") or "").strip() or None
                author = str(item.get("author") or "").strip() or None
                score = item.get("score")
                score_value = float(score) if isinstance(score, (int, float)) else None

                snippet = None
                summary = item.get("summary")
                if isinstance(summary, str) and summary.strip():
                    snippet = _compact_text(summary, max_len=snippet_max_len)
                else:
                    highlights = item.get("highlights")
                    if isinstance(highlights, list) and highlights:
                        first = highlights[0]
                        if isinstance(first, str) and first.strip():
                            snippet = _compact_text(first, max_len=snippet_max_len)
                    if not snippet:
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            snippet = _compact_text(text, max_len=snippet_max_len)

                results.append(
                    WebSearchResult(
                        title=title or url_item,
                        url=url_item,
                        published_date=published_date,
                        author=author,
                        score=score_value,
                        snippet=snippet,
                    )
                )

        out = WebSearchResponse(
            provider="exa",
            request_id=str(data.get("requestId") or data.get("request_id") or "").strip() or None
            if isinstance(data, dict)
            else None,
            total=len(results),
            results=results,
            cost=data.get("costDollars") if isinstance(data, dict) and isinstance(data.get("costDollars"), dict) else None,
        )

        self._cache_set(cache_key, out)
        return out
