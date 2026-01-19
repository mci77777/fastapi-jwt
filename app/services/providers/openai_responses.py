"""OpenAI Responses adapter (best-effort)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.auth import ProviderError
from app.core.middleware import REQUEST_ID_HEADER_NAME, get_current_request_id
from app.services.ai_url import normalize_ai_base_url
from app.services.upstream_auth import is_retryable_auth_error, iter_auth_headers

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)

_TRACE_UPSTREAM_RAW_MAX_FRAMES = 20
_TRACE_UPSTREAM_RAW_MAX_CHARS = 8000


class OpenAIResponsesAdapter:
    dialect = "openai.responses"

    def build_request(
        self,
        endpoint: dict[str, Any],
        payload: dict[str, Any],
        *,
        request_id: Optional[str] = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        base = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
        url = f"{base}/v1/responses" if base else "/v1/responses"
        # SSE 流式：显式禁用压缩，避免中间层 gzip 缓冲导致“看起来不流式”。
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream", "Accept-Encoding": "identity"}
        rid = request_id or get_current_request_id()
        if rid:
            headers[REQUEST_ID_HEADER_NAME] = rid

        body = dict(payload or {})
        body.setdefault("stream", True)
        return url, headers, body

    async def stream(
        self,
        *,
        endpoint: dict[str, Any],
        api_key: str,
        payload: dict[str, Any],
        timeout: float,
        publish: PublishFn,
        emit_raw: bool = False,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        url, base_headers, body = self.build_request(endpoint, payload)
        auth_candidates = iter_auth_headers(api_key, url) or [{"Authorization": f"Bearer {api_key}"}]

        reply_parts: list[str] = []
        upstream_request_id: Optional[str] = None
        usage: Optional[dict[str, Any]] = None
        raw_frames = 0
        raw_chars = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            for index, auth_headers in enumerate(auth_candidates):
                headers = dict(base_headers)
                headers.update(auth_headers)

                async with client.stream("POST", url, json=body, headers=headers) as response:
                    if response.status_code == 401 and index < len(auth_candidates) - 1:
                        retry_payload: object | None = None
                        try:
                            raw = await response.aread()
                            retry_payload = json.loads(raw) if raw else None
                        except Exception:
                            retry_payload = None
                        if is_retryable_auth_error(response.status_code, retry_payload):
                            continue
                    response.raise_for_status()

                    upstream_request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
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
                                    if (
                                        raw_frames < _TRACE_UPSTREAM_RAW_MAX_FRAMES
                                        and raw_chars < _TRACE_UPSTREAM_RAW_MAX_CHARS
                                    ):
                                        remaining = max(0, _TRACE_UPSTREAM_RAW_MAX_CHARS - raw_chars)
                                        chunk_text = text[:remaining] if remaining else ""
                                        if chunk_text:
                                            raw_frames += 1
                                            raw_chars += len(chunk_text)
                                            await publish(
                                                "upstream_raw",
                                                {
                                                    "dialect": self.dialect,
                                                    "upstream_event": None,
                                                    "raw": chunk_text,
                                                    "raw_truncated": len(chunk_text) < len(text),
                                                },
                                            )
                        else:
                            raw_bytes.extend(await response.aread())
                        raw = bytes(raw_bytes)
                        try:
                            data = json.loads(raw)
                        except Exception as exc:
                            if emit_raw:
                                payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                                return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                            raise ProviderError("upstream_invalid_response") from exc
                        text = _extract_any_text(data)
                        if not text:
                            if emit_raw:
                                payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                                return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                            raise ProviderError("upstream_empty_content")
                        await publish("content_delta", {"delta": text})
                        return text, json.dumps(data, ensure_ascii=False), upstream_request_id, None

                    async for event_name, raw_text in iter_sse_frames(response):
                        if emit_raw and raw_text:
                            if raw_frames < _TRACE_UPSTREAM_RAW_MAX_FRAMES and raw_chars < _TRACE_UPSTREAM_RAW_MAX_CHARS:
                                remaining = max(0, _TRACE_UPSTREAM_RAW_MAX_CHARS - raw_chars)
                                chunk = raw_text[:remaining] if remaining else ""
                                if chunk:
                                    raw_frames += 1
                                    raw_chars += len(chunk)
                                    await publish(
                                        "upstream_raw",
                                        {
                                            "dialect": self.dialect,
                                            "upstream_event": event_name,
                                            "raw": chunk,
                                            "raw_truncated": len(chunk) < len(raw_text),
                                        },
                                    )
                        if raw_text == "[DONE]":
                            break
                        if not raw_text:
                            continue
                        try:
                            obj = json.loads(raw_text)
                        except Exception:
                            continue

                        candidate_usage = obj.get("usage") if isinstance(obj, dict) else None
                        if isinstance(candidate_usage, dict):
                            usage = dict(candidate_usage)

                        if isinstance(obj, dict) and obj.get("error"):
                            raise ProviderError("upstream_error")

                        event_type = str(obj.get("type") or "").strip()
                        if event_type.endswith(".delta"):
                            delta = obj.get("delta")
                            if isinstance(delta, str) and delta:
                                reply_parts.append(delta)
                                await publish("content_delta", {"delta": delta})
                                continue
                            text = obj.get("text")
                            if isinstance(text, str) and text:
                                reply_parts.append(text)
                                await publish("content_delta", {"delta": text})
                                continue

                        if event_type.endswith(".completed") or event_type == "response.completed":
                            break

                    reply_text = "".join(reply_parts).strip()
                    if not reply_text:
                        if emit_raw:
                            payload_out: dict[str, Any] = {"stream": True, "chunks": len(reply_parts), "raw_only": True}
                            if usage:
                                payload_out["usage"] = usage
                            return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                        raise ProviderError("upstream_empty_content")
                    payload_out: dict[str, Any] = {"stream": True, "chunks": len(reply_parts)}
                    if usage:
                        payload_out["usage"] = usage
                    return (
                        reply_text,
                        json.dumps(payload_out, ensure_ascii=False),
                        upstream_request_id,
                        None,
                    )

        raise ProviderError("upstream_no_response")


def _extract_any_text(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    if isinstance(obj.get("output_text"), str) and obj.get("output_text").strip():
        return str(obj.get("output_text")).strip()
    output = obj.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"]:
                        parts.append(c["text"])
        text = "".join(parts).strip()
        if text:
            return text
    return ""


def _stream_chunks(text: str, chunk_size: int = 120):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
