"""Anthropic Messages adapter."""

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

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)

_TRACE_UPSTREAM_RAW_MAX_FRAMES = 20
_TRACE_UPSTREAM_RAW_MAX_CHARS = 8000


class AnthropicMessagesAdapter:
    dialect = "anthropic.messages"

    def _format_upstream_error(self, raw: bytes) -> str:
        try:
            data = json.loads(raw)
        except Exception:
            text = raw.decode("utf-8", errors="replace").strip()
            return text[:240] if text else "unknown_error"

        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                msg = err.get("message") or err.get("error") or err.get("type")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()[:240]
            msg = data.get("message") or data.get("msg") or data.get("detail")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:240]
            return json.dumps(data, ensure_ascii=False)[:240]

        return str(data)[:240]

    def build_request(
        self,
        endpoint: dict[str, Any],
        payload: dict[str, Any],
        *,
        api_key: str,
        request_id: Optional[str] = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        base_url = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
        url = f"{base_url}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            # SSE 流式：显式禁用压缩，避免中间层 gzip 缓冲导致“看起来不流式”。
            "Accept-Encoding": "identity",
        }
        rid = request_id or get_current_request_id()
        if rid:
            headers[REQUEST_ID_HEADER_NAME] = rid
        return url, headers, payload

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
        url, headers, body = self.build_request(endpoint, payload, api_key=api_key)

        reply_parts: list[str] = []
        upstream_request_id: Optional[str] = None
        usage: Optional[dict[str, Any]] = None
        raw_frames = 0
        raw_chars = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raw = await response.aread()
                    detail = self._format_upstream_error(raw)
                    raise ProviderError(f"upstream_http_{response.status_code}:{detail}") from exc
                upstream_request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
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
                    blocks = data.get("content") if isinstance(data, dict) else None
                    if not isinstance(blocks, list):
                        if emit_raw:
                            payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                            return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                        raise ProviderError("upstream_invalid_response")
                    text = "".join(
                        block.get("text", "")
                        for block in blocks
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                    if not text:
                        if emit_raw:
                            payload_out = {"stream": False, "raw_len": len(raw), "raw_only": True}
                            return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                        raise ProviderError("upstream_empty_content")
                    reply_text = text.strip()
                    await publish("content_delta", {"delta": reply_text})
                    return reply_text, json.dumps(data, ensure_ascii=False), upstream_request_id, None

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

                    if event_name == "error" or (isinstance(obj, dict) and obj.get("type") == "error"):
                        raise ProviderError("upstream_error")

                    if event_name == "content_block_delta" and isinstance(obj, dict):
                        delta = obj.get("delta") if isinstance(obj.get("delta"), dict) else None
                        if delta and delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                reply_parts.append(text)
                                await publish("content_delta", {"delta": text})

                    if event_name == "message_stop":
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


def _stream_chunks(text: str, chunk_size: int = 120):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
