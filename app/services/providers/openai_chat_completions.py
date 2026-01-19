"""OpenAI Chat Completions adapter."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import httpx

from app.auth import ProviderError
from app.core.middleware import REQUEST_ID_HEADER_NAME, get_current_request_id
from app.services.ai_url import build_resolved_endpoints, normalize_ai_base_url
from app.services.upstream_auth import is_retryable_auth_error, iter_auth_headers

from .sse import iter_sse_frames

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)

_TRACE_UPSTREAM_RAW_MAX_FRAMES = 20
_TRACE_UPSTREAM_RAW_MAX_CHARS = 8000


class OpenAIChatCompletionsAdapter:
    dialect = "openai.chat_completions"

    def build_request(
        self,
        endpoint: dict[str, Any],
        openai_req: dict[str, Any],
        *,
        request_id: Optional[str] = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        resolved = endpoint.get("resolved_endpoints") or {}
        chat_url = resolved.get("chat_completions")
        computed = build_resolved_endpoints(str(endpoint.get("base_url") or "")).get("chat_completions")
        if isinstance(computed, str) and computed.strip():
            computed = computed.strip()
            if (
                not isinstance(chat_url, str)
                or not chat_url.strip()
                or chat_url.strip() != computed
                or "/v1/v1/" in chat_url
                or "/chat/completions/v1/chat/completions" in chat_url
            ):
                chat_url = computed
        elif (
            not isinstance(chat_url, str)
            or not chat_url.strip()
            or "/v1/v1/" in chat_url
            or "/chat/completions/v1/chat/completions" in chat_url
        ):
            base = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
            chat_url = f"{base}/v1/chat/completions" if base else "/v1/chat/completions"

        # SSE 流式：显式禁用压缩，避免中间层 gzip 缓冲导致“看起来不流式”。
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream", "Accept-Encoding": "identity"}
        rid = request_id or get_current_request_id()
        if rid:
            headers[REQUEST_ID_HEADER_NAME] = rid

        # payload 模式：允许在白名单范围内全量透传；SSOT：服务端强制 stream=true
        payload = {str(k): v for k, v in (openai_req or {}).items() if v is not None}
        payload["stream"] = True

        return str(chat_url), headers, payload

    async def stream(
        self,
        *,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
        timeout: float,
        publish: PublishFn,
        emit_raw: bool = False,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        """Stream upstream SSE and publish normalized events.

        Returns: (reply_text, response_payload, upstream_request_id, metadata)
        """

        url, base_headers, payload = self.build_request(endpoint, openai_req)
        auth_candidates = iter_auth_headers(api_key, url) or [{"Authorization": f"Bearer {api_key}"}]

        reply_parts: list[str] = []
        tool_call_names: list[str] = []
        saw_function_call = False
        upstream_request_id: Optional[str] = None
        usage: Optional[dict[str, Any]] = None
        raw_frames = 0
        raw_chars = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            for index, auth_headers in enumerate(auth_candidates):
                headers = dict(base_headers)
                headers.update(auth_headers)

                async with client.stream("POST", url, json=payload, headers=headers) as response:
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
                                return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, None
                            raise ProviderError("upstream_invalid_response") from exc

                        choices = data.get("choices") if isinstance(data, dict) else None
                        if not isinstance(choices, list) or not choices:
                            raise ProviderError("upstream_empty_choices")

                        choice0 = choices[0] if isinstance(choices[0], dict) else {}
                        msg = choice0.get("message") if isinstance(choice0, dict) else None
                        msg = msg if isinstance(msg, dict) else {}
                        content = msg.get("content", "")
                        if not content:
                            tool_calls = msg.get("tool_calls")
                            if isinstance(tool_calls, list) and tool_calls:
                                names = _collect_tool_call_names(tool_calls)
                                suffix = f" tools={','.join(names[:5])}" if names else ""
                                raise ProviderError(f"tool_calls_not_supported{suffix}")
                            function_call = msg.get("function_call")
                            if isinstance(function_call, dict) and function_call.get("name"):
                                raise ProviderError("function_call_not_supported")
                            raise ProviderError("upstream_empty_content")

                        reply_text = str(content).strip()
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

                        if isinstance(obj, dict) and obj.get("error"):
                            raise ProviderError("upstream_error")

                        choices = obj.get("choices") if isinstance(obj, dict) else None
                        if not isinstance(choices, list) or not choices:
                            continue

                        choice0 = choices[0] if isinstance(choices[0], dict) else {}
                        delta = choice0.get("delta") if isinstance(choice0.get("delta"), dict) else None
                        if not isinstance(delta, dict):
                            continue

                        tool_calls = delta.get("tool_calls")
                        if isinstance(tool_calls, list) and tool_calls:
                            tool_call_names.extend(_collect_tool_call_names(tool_calls))

                        function_call = delta.get("function_call")
                        if isinstance(function_call, dict) and function_call.get("name"):
                            saw_function_call = True

                        reasoning = delta.get("reasoning_content")
                        if isinstance(reasoning, str) and reasoning:
                            reply_parts.append(reasoning)
                            await publish("content_delta", {"delta": reasoning})

                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            reply_parts.append(text)
                            await publish("content_delta", {"delta": text})

                    reply_text = "".join(reply_parts).strip()
                    if reply_text:
                        metadata = None
                        names = list(dict.fromkeys([x for x in tool_call_names if x]))
                        if names:
                            metadata = {"tool_calls": {"names": names[:20]}}
                        payload_out: dict[str, Any] = {"stream": True, "chunks": len(reply_parts)}
                        if usage:
                            payload_out["usage"] = usage
                        return (
                            reply_text,
                            json.dumps(payload_out, ensure_ascii=False),
                            upstream_request_id,
                            metadata,
                        )

                    names = list(dict.fromkeys([x for x in tool_call_names if x]))
                    if emit_raw:
                        metadata = None
                        if names or saw_function_call:
                            metadata = {"tool_calls": {"names": names[:20]}, "saw_function_call": bool(saw_function_call)}
                        payload_out: dict[str, Any] = {"stream": True, "chunks": len(reply_parts), "raw_only": True}
                        if usage:
                            payload_out["usage"] = usage
                        return "", json.dumps(payload_out, ensure_ascii=False), upstream_request_id, metadata

                    if names:
                        suffix = f" tools={','.join(names[:5])}" if names else ""
                        raise ProviderError(f"tool_calls_not_supported{suffix}")
                    if saw_function_call:
                        raise ProviderError("function_call_not_supported")
                    raise ProviderError("upstream_empty_content")

        raise ProviderError("upstream_no_response")


def _collect_tool_call_names(tool_calls: list[Any]) -> list[str]:
    names: list[str] = []
    for item in tool_calls:
        fn = item.get("function") if isinstance(item, dict) else None
        if isinstance(fn, dict):
            name = fn.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return list(dict.fromkeys(names))


def _stream_chunks(text: str, chunk_size: int = 120):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
