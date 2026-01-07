"""Gemini streamGenerateContent adapter (best-effort)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.auth import ProviderError
from app.core.middleware import get_current_request_id
from app.services.ai_url import normalize_ai_base_url

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class GeminiGenerateContentAdapter:
    dialect = "gemini.generate_content"

    def build_request(
        self,
        endpoint: dict[str, Any],
        *,
        model: str,
        api_key: str,
        payload: dict[str, Any],
        request_id: Optional[str] = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        base = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
        model_name = str(model or "").strip()
        if not model_name:
            raise ProviderError("model_required")
        url = f"{base}/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        rid = request_id or get_current_request_id()
        if rid:
            headers["X-Request-Id"] = rid
        return url, headers, payload

    async def stream(
        self,
        *,
        endpoint: dict[str, Any],
        api_key: str,
        model: str,
        payload: dict[str, Any],
        timeout: float,
        publish: PublishFn,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        url, headers, body = self.build_request(endpoint, model=model, api_key=api_key, payload=payload)
        reply_parts: list[str] = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                response.raise_for_status()

                content_type = str(response.headers.get("content-type") or "").lower()
                if "text/event-stream" not in content_type:
                    raw = await response.aread()
                    try:
                        data = json.loads(raw)
                    except Exception as exc:
                        raise ProviderError("upstream_invalid_response") from exc
                    text = _extract_text_from_chunk(data)
                    if not text:
                        raise ProviderError("upstream_empty_content")
                    for chunk in _stream_chunks(text):
                        await publish("content_delta", {"delta": chunk})
                    return text, json.dumps(data, ensure_ascii=False), None, None

                async for _, raw_text in iter_sse_frames(response):
                    if raw_text == "[DONE]":
                        break
                    if not raw_text:
                        continue
                    try:
                        obj = json.loads(raw_text)
                    except Exception:
                        continue

                    text = _extract_text_from_chunk(obj)
                    if text:
                        reply_parts.append(text)
                        await publish("content_delta", {"delta": text})

        reply_text = "".join(reply_parts).strip()
        if not reply_text:
            raise ProviderError("upstream_empty_content")
        return reply_text, json.dumps({"stream": True, "chunks": len(reply_parts)}, ensure_ascii=False), None, None


def _extract_text_from_chunk(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    candidates = obj.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    cand0 = candidates[0] if isinstance(candidates[0], dict) else {}
    content = cand0.get("content") if isinstance(cand0.get("content"), dict) else None
    parts = (content or {}).get("parts")
    if isinstance(parts, list) and parts:
        p0 = parts[0] if isinstance(parts[0], dict) else {}
        text = p0.get("text")
        if isinstance(text, str) and text:
            return text
    return ""


def _stream_chunks(text: str, chunk_size: int = 120):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]

