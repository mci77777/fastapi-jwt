"""Gemini streamGenerateContent adapter (best-effort)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.auth import ProviderError
from app.core.middleware import get_current_request_id
from app.services.ai_url import normalize_ai_base_url

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)

_DEFAULT_TEXT_CHUNK_SIZE = 24


def _iter_text_chunks(text: str, *, chunk_size: int = _DEFAULT_TEXT_CHUNK_SIZE):
    if not text:
        return
    size = max(int(chunk_size or _DEFAULT_TEXT_CHUNK_SIZE), 1)
    for index in range(0, len(text), size):
        yield text[index : index + size]


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
        # SSE 流式：显式禁用压缩，避免中间层 gzip 缓冲导致“看起来不流式”。
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream", "Accept-Encoding": "identity"}
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
        emit_raw: bool = False,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        url, headers, body = self.build_request(endpoint, model=model, api_key=api_key, payload=payload)
        reply_parts: list[str] = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                response.raise_for_status()

                content_type = str(response.headers.get("content-type") or "").lower()
                if "text/event-stream" not in content_type:
                    logger.warning(
                        "[UPSTREAM_NOT_SSE] ts=%s dialect=%s status=%s content_type=%s",
                        int(time.time() * 1000),
                        self.dialect,
                        response.status_code,
                        content_type,
                    )
                    raw_bytes = bytearray()
                    if emit_raw and hasattr(response, "aiter_bytes"):
                        async for chunk in response.aiter_bytes():
                            if not chunk:
                                continue
                            raw_bytes.extend(chunk)
                            try:
                                text = chunk.decode("utf-8", errors="replace")
                            except Exception:
                                text = ""
                            if text:
                                await publish(
                                    "upstream_raw",
                                    {"dialect": self.dialect, "upstream_event": None, "raw": text},
                                )
                    else:
                        raw_bytes.extend(await response.aread())
                    raw = bytes(raw_bytes)
                    try:
                        data = json.loads(raw)
                    except Exception as exc:
                        if emit_raw:
                            payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                            return "", json.dumps(payload_out, ensure_ascii=False), None, None
                        raise ProviderError("upstream_invalid_response") from exc
                    text = _extract_text_from_chunk(data)
                    if not text:
                        if emit_raw:
                            payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                            return "", json.dumps(payload_out, ensure_ascii=False), None, None
                        raise ProviderError("upstream_empty_content")
                    for chunk in _iter_text_chunks(text):
                        await publish("content_delta", {"delta": chunk})
                    return text, json.dumps(data, ensure_ascii=False), None, None

                async for event_name, raw_text in iter_sse_frames(response):
                    if emit_raw and raw_text:
                        await publish(
                            "upstream_raw",
                            {"dialect": self.dialect, "upstream_event": event_name, "raw": raw_text},
                        )
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
                        for chunk in _iter_text_chunks(text):
                            await publish("content_delta", {"delta": chunk})

        reply_text = "".join(reply_parts).strip()
        if not reply_text:
            if emit_raw:
                return "", json.dumps({"stream": True, "chunks": len(reply_parts), "raw_only": True}, ensure_ascii=False), None, None
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
