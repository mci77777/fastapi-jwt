"""Anthropic Messages adapter."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.auth import ProviderError
from app.core.middleware import REQUEST_ID_HEADER_NAME, get_current_request_id
from app.services.ai_url import normalize_ai_base_url

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class AnthropicMessagesAdapter:
    dialect = "anthropic.messages"

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
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        url, headers, body = self.build_request(endpoint, payload, api_key=api_key)

        reply_parts: list[str] = []
        upstream_request_id: Optional[str] = None
        usage: Optional[dict[str, Any]] = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                response.raise_for_status()
                upstream_request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
                content_type = str(response.headers.get("content-type") or "").lower()

                if "text/event-stream" not in content_type:
                    raw = await response.aread()
                    try:
                        data = json.loads(raw)
                    except Exception as exc:
                        raise ProviderError("upstream_invalid_response") from exc
                    blocks = data.get("content") if isinstance(data, dict) else None
                    if not isinstance(blocks, list):
                        raise ProviderError("upstream_invalid_response")
                    text = "".join(
                        block.get("text", "")
                        for block in blocks
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                    if not text:
                        raise ProviderError("upstream_empty_content")
                    reply_text = text.strip()
                    for chunk in _stream_chunks(reply_text):
                        await publish("content_delta", {"delta": chunk})
                    return reply_text, json.dumps(data, ensure_ascii=False), upstream_request_id, None

                async for event_name, raw_text in iter_sse_frames(response):
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
