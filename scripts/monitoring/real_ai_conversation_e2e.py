#!/usr/bin/env python3
"""
真实上游 E2E（多轮对话 + 多次重复）：
1) Dashboard 本地 admin 登录（/api/v1/base/access_token）获取 JWT
2) 用 assets/prompts 的 SSOT 写入并 activate prompts（避免 DB 影子 prompt；支持 ThinkingML 与 JSONSeq）
3) GET /api/v1/llm/models?view=mapped，按 mapping 名称逐个发起对话
4) POST /api/v1/messages -> GET /events 消费 GymBro SSE：
   - thinkingml_v45：拼接 content_delta 并按 docs/ai预期响应结构.md（ThinkingML v4.5）校验
   - jsonseq_v1：按事件流校验 docs/ai_jsonseq_v1_预期响应结构.md（JSONSeq v1）

默认目标：优先跑 xai + deepseek（可用 --models 指定，或留空跑全部 mapped models）。

退出码：
  0 通过
  2 前置条件缺失（服务不可用/模型未配置）
  3 运行失败（任一轮次 FAIL）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

# 复用同一份契约校验器（SSOT：local_mock_ai_conversation_e2e.py）
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.monitoring.local_mock_ai_conversation_e2e import (  # noqa: E402
    _load_prompt_assets,
    _parse_tools_from_tool_md,
    _validate_jsonseq_v1_events,
    _validate_thinkingml,
)


REQUEST_ID_HEADER = "X-Request-Id"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_api_base(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:9999/api/v1"
    text = text.rstrip("/")
    if text.endswith("/api/v1"):
        return text
    return text + "/api/v1"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real upstream AI conversation E2E (ThinkingML contract)")
    parser.add_argument("--api-base", default=os.getenv("E2E_API_BASE", "http://127.0.0.1:9999/api/v1"))
    parser.add_argument("--username", default=os.getenv("E2E_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("E2E_ADMIN_PASSWORD", "123456"))
    parser.add_argument("--models", nargs="*", default=None, help="映射名列表（如 xai deepseek）；不传则跑全部 mapped models")
    parser.add_argument("--runs", type=int, default=_as_int(os.getenv("E2E_RUNS"), 1))
    parser.add_argument("--turns", type=int, default=_as_int(os.getenv("E2E_TURNS"), 1))
    parser.add_argument(
        "--prompt-text",
        default=os.getenv("E2E_PROMPT_TEXT", ""),
        help="可选：覆盖第 1 轮用户输入（用于复现/回归特定场景）。",
    )
    parser.add_argument(
        "--tool-choice",
        default=os.getenv("E2E_TOOL_CHOICE", "none"),
        help="OpenAI tool_choice：auto/none/required。默认 none（避免后端 tool_calls 未实现导致结构不稳定）。",
    )
    parser.add_argument(
        "--app-output-protocol",
        default=os.getenv("E2E_APP_OUTPUT_PROTOCOL", "thinkingml_v45"),
        choices=["thinkingml_v45", "jsonseq_v1"],
        help="App 对外输出协议：thinkingml_v45=旧 SSE(content_delta)；jsonseq_v1=事件流(final_delta/phase_*)。",
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=float(os.getenv("E2E_THROTTLE_SECONDS", "0.35")),
        help="为避免 IP QPS 限流，对 E2E 初始化请求做节流（单位：秒）。",
    )
    parser.add_argument("--stream-timeout", type=float, default=float(os.getenv("E2E_STREAM_TIMEOUT", "180")))
    parser.add_argument("--max-events", type=int, default=_as_int(os.getenv("E2E_MAX_EVENTS", 4000), 4000))
    parser.add_argument("--artifacts-dir", default=os.getenv("E2E_ARTIFACTS_DIR", "e2e/real_ai_conversation/artifacts"))
    parser.add_argument("--verbose", action="store_true", default=str(os.getenv("E2E_VERBOSE", "1")).strip().lower() in ("1", "true", "yes"))
    return parser.parse_args()


def _print(msg: str, *, verbose: bool) -> None:
    if verbose:
        print(msg)


def _normalize_model_key(value: str) -> str:
    return str(value or "").strip().lower()


def _resolve_mapped_model_name(name: str, *, mapped_by_lower: dict[str, str]) -> str | None:
    """把用户输入的模型名解析为 /llm/models?view=mapped 返回的真实 name。"""

    raw = str(name or "").strip()
    if not raw:
        return None

    lowered = _normalize_model_key(raw)
    if lowered in mapped_by_lower:
        return mapped_by_lower[lowered]

    # 兼容：历史/别名（不改变后端 SSOT，仅用于脚本选择）
    alias_candidates: dict[str, tuple[str, ...]] = {
        # 某些环境映射名为 grok/GROK；历史也可能叫 xai
        "grok": ("grok", "xai"),
        "x.ai": ("xai", "grok"),
        "xai": ("xai", "grok"),
    }
    for candidate in alias_candidates.get(lowered, ()):
        if candidate in mapped_by_lower:
            return mapped_by_lower[candidate]
    return None


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


async def _login(client: httpx.AsyncClient, *, username: str, password: str, verbose: bool) -> str:
    request_id = uuid.uuid4().hex
    resp = await client.post(
        "/base/access_token",
        json={"username": username, "password": password},
        headers={REQUEST_ID_HEADER: request_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = _unwrap_data(resp.json()) or {}
    token = str((data or {}).get("access_token") or "").strip()
    if not token:
        raise RuntimeError("missing_access_token")
    _print(f"[login] ok request_id={request_id}", verbose=verbose)
    return token


async def _ensure_prompt(
    client: httpx.AsyncClient,
    *,
    auth_headers: dict[str, str],
    name: str,
    prompt_type: str,
    content: str,
    version: str,
    category: str,
    description: str,
    tools_json: Any | None,
    throttle_seconds: float,
    verbose: bool,
) -> int:
    request_id = uuid.uuid4().hex
    resp = await client.get(
        "/llm/prompts",
        params={"keyword": name, "prompt_type": prompt_type, "page": 1, "page_size": 50},
        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    if throttle_seconds > 0:
        await asyncio.sleep(throttle_seconds)
    items = _unwrap_data(resp.json()) or []

    candidates: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "") == name and str(item.get("prompt_type") or "") == prompt_type:
                candidates.append(item)

    prompt_id: int | None = None
    if candidates:
        prompt_id = max([_as_int(item.get("id"), 0) for item in candidates] or [0])
        _print(f"[prompt] reuse name={name} type={prompt_type} id={prompt_id}", verbose=verbose)

    payload: dict[str, Any] = {
        "name": name,
        "prompt_type": prompt_type,
        "content": content,
        "version": version,
        "category": category,
        "description": description,
    }
    if tools_json is not None:
        payload["tools_json"] = tools_json

    if prompt_id:
        request_id = uuid.uuid4().hex
        updated = await client.put(
            f"/llm/prompts/{prompt_id}",
            json={k: v for k, v in payload.items() if k != "name"},
            headers={**auth_headers, REQUEST_ID_HEADER: request_id},
            timeout=30.0,
        )
        updated.raise_for_status()
        if throttle_seconds > 0:
            await asyncio.sleep(throttle_seconds)
        _print(f"[prompt] updated id={prompt_id} request_id={request_id}", verbose=verbose)
    else:
        request_id = uuid.uuid4().hex
        created = await client.post(
            "/llm/prompts",
            json=payload,
            headers={**auth_headers, REQUEST_ID_HEADER: request_id},
            timeout=30.0,
        )
        created.raise_for_status()
        if throttle_seconds > 0:
            await asyncio.sleep(throttle_seconds)
        created_data = _unwrap_data(created.json()) or {}
        prompt_id = _as_int((created_data or {}).get("id"), 0)
        if not prompt_id:
            raise RuntimeError("prompt_create_missing_id")
        _print(f"[prompt] created id={prompt_id} request_id={request_id}", verbose=verbose)

    request_id = uuid.uuid4().hex
    activated = await client.post(
        f"/llm/prompts/{prompt_id}/activate",
        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
        timeout=30.0,
    )
    activated.raise_for_status()
    if throttle_seconds > 0:
        await asyncio.sleep(throttle_seconds)
    _print(f"[prompt] activated id={prompt_id} request_id={request_id}", verbose=verbose)
    return int(prompt_id)


async def _collect_sse_events(
    client: httpx.AsyncClient,
    *,
    message_id: str,
    conversation_id: str,
    auth_headers: dict[str, str],
    request_id: str,
    stream_timeout: float,
    max_events: int,
) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    reply_accum = ""

    url = f"/messages/{message_id}/events"
    params = {"conversation_id": conversation_id}

    async with client.stream(
        "GET",
        url,
        params=params,
        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
        timeout=stream_timeout,
    ) as response:
        response.raise_for_status()

        current_event = "message"
        data_lines: list[str] = []

        async def flush() -> dict[str, Any] | None:
            nonlocal data_lines, reply_accum
            if not data_lines:
                return None
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            evt = {"event": current_event, "data": parsed}
            if current_event == "content_delta" and isinstance(parsed, dict) and parsed.get("delta"):
                reply_accum += str(parsed.get("delta"))
            if current_event == "final_delta" and isinstance(parsed, dict) and parsed.get("text"):
                reply_accum += str(parsed.get("text"))
            return evt

        async for line in response.aiter_lines():
            if line is None:
                continue
            line = line.rstrip("\r")
            if line == "":
                evt = await flush()
                if evt:
                    events.append(evt)
                    if evt["event"] in {"completed", "error"}:
                        break
                    if len(events) >= max_events:
                        raise RuntimeError("SSE 事件数量超限（可能未正常结束）")
                current_event = "message"
                continue
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
                continue

        evt = await flush()
        if evt:
            events.append(evt)

    return events, reply_accum


def _extract_routed(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for evt in events:
        if evt.get("event") != "status":
            continue
        data = evt.get("data")
        if isinstance(data, dict) and data.get("state") == "routed":
            return data
    return None


def _extract_error(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for evt in events:
        if evt.get("event") == "error":
            data = evt.get("data")
            return data if isinstance(data, dict) else {"message": str(data)}
    return None


def _should_retry_without_tools(error_message: str) -> bool:
    text = str(error_message or "").lower()
    if not text:
        return False
    if "tool" not in text and "function" not in text:
        return False
    hints = (
        "unsupported",
        "not supported",
        "not_supported",
        "tool_calls_not_supported",
        "function_call_not_supported",
        "unknown",
        "unrecognized",
        "invalid",
        "not allowed",
        "unexpected",
    )
    return any(h in text for h in hints)


@dataclass
class TurnResult:
    ok: bool
    reason: str
    request_id: str
    message_id: str
    conversation_id: str
    provider: str | None
    resolved_model: str | None
    endpoint_id: int | None
    upstream_request_id: str | None
    reply_text: str
    retried_without_tools: bool
    sse_error: str | None
    event_counts: dict[str, int]


async def _run_single_turn(
    client: httpx.AsyncClient,
    *,
    auth_headers: dict[str, str],
    model: str,
    app_output_protocol: str,
    conversation_id: str,
    messages: list[dict[str, Any]],
    tool_choice: str | None,
    temperature: float | None,
    stream_timeout: float,
    max_events: int,
    verbose: bool,
) -> TurnResult:
    request_id = uuid.uuid4().hex

    async def send(*, tool_choice_value: str | None) -> tuple[dict[str, Any], list[dict[str, Any]], str, str | None, dict[str, int]]:
        payload: dict[str, Any] = {
            "conversation_id": conversation_id,
            "metadata": {"save_history": False},
            "model": model,
            "messages": messages,
            "skip_prompt": False,
        }
        if isinstance(tool_choice_value, str) and tool_choice_value.strip():
            payload["tool_choice"] = tool_choice_value.strip()
        if temperature is not None:
            payload["temperature"] = temperature

        resp = await client.post(
            "/messages",
            json=payload,
            headers={**auth_headers, REQUEST_ID_HEADER: request_id},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        message_id = str((data.get("message_id") or "")).strip()
        conv_id = str((data.get("conversation_id") or "")).strip()
        if not message_id or not conv_id:
            raise RuntimeError("missing_message_or_conversation_id")
        events, reply = await _collect_sse_events(
            client,
            message_id=message_id,
            conversation_id=conv_id,
            auth_headers=auth_headers,
            request_id=request_id,
            stream_timeout=stream_timeout,
            max_events=max_events,
        )
        counts: dict[str, int] = {}
        for evt in events:
            name = str(evt.get("event") or "message")
            counts[name] = counts.get(name, 0) + 1
        routed = _extract_routed(events) or {}
        err = _extract_error(events)
        err_text = str(err.get("message") or err.get("error") or "") if isinstance(err, dict) else str(err or "")
        provider = str(routed.get("provider") or "") or None
        resolved_model = str(routed.get("resolved_model") or "") or None
        upstream_request_id = str(routed.get("upstream_request_id") or "") or None
        endpoint_id_raw = routed.get("endpoint_id")
        endpoint_id = int(endpoint_id_raw) if isinstance(endpoint_id_raw, int) else None
        return (
            {
                "message_id": message_id,
                "conversation_id": conv_id,
                "provider": provider,
                "resolved_model": resolved_model,
                "endpoint_id": endpoint_id,
                "upstream_request_id": upstream_request_id,
                "events": events,
            },
            events,
            reply,
            err_text or None,
            counts,
        )

    try:
        meta, events, reply_text, sse_error, event_counts = await send(tool_choice_value=tool_choice)
        protocol = str(app_output_protocol or "thinkingml_v45").strip().lower() or "thinkingml_v45"
        if protocol == "jsonseq_v1":
            ok, reason = _validate_jsonseq_v1_events(events)
        else:
            ok, reason = _validate_thinkingml(reply_text)
        if ok:
            return TurnResult(
                ok=True,
                reason=reason,
                request_id=request_id,
                message_id=meta["message_id"],
                conversation_id=meta["conversation_id"],
                provider=meta["provider"],
                resolved_model=meta["resolved_model"],
                endpoint_id=meta["endpoint_id"],
                upstream_request_id=meta["upstream_request_id"],
                reply_text=reply_text,
                retried_without_tools=False,
                sse_error=sse_error,
                event_counts=event_counts,
            )

        if sse_error and _should_retry_without_tools(sse_error):
            _print(f"[retry] model={model} request_id={request_id} reason=tools_not_supported", verbose=verbose)
            meta, events, reply_text, sse_error, event_counts = await send(tool_choice_value=None)
            protocol = str(app_output_protocol or "thinkingml_v45").strip().lower() or "thinkingml_v45"
            if protocol == "jsonseq_v1":
                ok, reason = _validate_jsonseq_v1_events(events)
            else:
                ok, reason = _validate_thinkingml(reply_text)
            return TurnResult(
                ok=ok,
                reason=reason if ok else f"{reason}|retried_without_tools",
                request_id=request_id,
                message_id=meta["message_id"],
                conversation_id=meta["conversation_id"],
                provider=meta["provider"],
                resolved_model=meta["resolved_model"],
                endpoint_id=meta["endpoint_id"],
                upstream_request_id=meta["upstream_request_id"],
                reply_text=reply_text,
                retried_without_tools=True,
                sse_error=sse_error,
                event_counts=event_counts,
            )

        return TurnResult(
            ok=False,
            reason=f"sse_error:{sse_error}" if sse_error and reason in ("empty_reply", "missing_required_blocks") else reason,
            request_id=request_id,
            message_id=meta["message_id"],
            conversation_id=meta["conversation_id"],
            provider=meta["provider"],
            resolved_model=meta["resolved_model"],
            endpoint_id=meta["endpoint_id"],
            upstream_request_id=meta["upstream_request_id"],
            reply_text=reply_text,
            retried_without_tools=False,
            sse_error=sse_error,
            event_counts=event_counts,
        )
    except Exception as exc:
        return TurnResult(
            ok=False,
            reason=f"exception:{type(exc).__name__}",
            request_id=request_id,
            message_id="",
            conversation_id=conversation_id,
            provider=None,
            resolved_model=None,
            endpoint_id=None,
            upstream_request_id=None,
            reply_text="",
            retried_without_tools=False,
            sse_error=None,
            event_counts={},
        )


def _turn_prompts(turns: int, *, first_turn_text: str | None = None) -> list[str]:
    base = [
        "给我一份三分化训练方案，适合新手，包含动作与每周频率。",
        "请把每次训练的热身与收操补齐，并把总时长控制在 60 分钟内。",
        "用 RPE 给出强度建议，并说明如何做渐进超负荷。",
    ]
    override = str(first_turn_text or "").strip()
    if override:
        if base:
            base[0] = override
        else:
            base = [override]
    if turns <= len(base):
        return base[:turns]
    more = [f"把第 {i+1} 轮建议进一步量化（组数/次数/休息）。" for i in range(len(base), turns)]
    return base + more


async def main() -> int:
    args = _parse_args()
    api_base = _normalize_api_base(args.api_base)
    artifacts_dir = (REPO_ROOT / str(args.artifacts_dir)).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / ".gitkeep").write_text("", encoding="utf-8")

    output_protocol = str(args.app_output_protocol or "thinkingml_v45").strip().lower() or "thinkingml_v45"
    profile, serp_prompt, tool_prompt = _load_prompt_assets(output_protocol=output_protocol)
    tools_schema_source = (REPO_ROOT / "assets" / "prompts" / "tool.md").read_text(encoding="utf-8").strip()
    tools_schema = _parse_tools_from_tool_md(tools_schema_source)
    profile_version = str((profile or {}).get("version") or "").strip() or "v1"
    prompt_type_system = "system"
    prompt_type_tools = "tools"
    if output_protocol == "jsonseq_v1":
        prompt_type_system = "system_jsonseq_v1"
        prompt_type_tools = "tools_jsonseq_v1"

    async with httpx.AsyncClient(base_url=api_base) as client:
        try:
            token = await _login(client, username=args.username, password=args.password, verbose=args.verbose)
        except Exception as exc:
            print(f"FAIL login reason={type(exc).__name__}")
            return 2

        auth_headers = {"Authorization": f"Bearer {token}"}

        try:
            await _ensure_prompt(
                client,
                auth_headers=auth_headers,
                name="SSOT:standard_serp_system" if output_protocol != "jsonseq_v1" else "SSOT:standard_jsonseq_v1_system",
                prompt_type=prompt_type_system,
                content=serp_prompt,
                version=profile_version,
                category="ssot",
                description="Strict XML / ThinkingML v4.5 system prompt (serp)"
                if output_protocol != "jsonseq_v1"
                else "JSONSeq v1 system prompt (events)",
                tools_json=None,
                throttle_seconds=float(args.throttle_seconds),
                verbose=args.verbose,
            )
            await _ensure_prompt(
                client,
                auth_headers=auth_headers,
                name="SSOT:standard_serp_tools" if output_protocol != "jsonseq_v1" else "SSOT:standard_jsonseq_v1_tools",
                prompt_type=prompt_type_tools,
                content=tool_prompt,
                version=profile_version,
                category="ssot",
                description="ToolCall patch (does not change Strict XML output protocol)"
                if output_protocol != "jsonseq_v1"
                else "ToolCall patch (does not change JSONSeq v1 output protocol)",
                tools_json=tools_schema,
                throttle_seconds=float(args.throttle_seconds),
                verbose=args.verbose,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = (exc.response.text or "") if exc.response is not None else ""
            body = body[:400]
            print(f"FAIL prompt_activate status={status} body={body}")
            return 3
        except Exception as exc:
            print(f"FAIL prompt_activate reason={type(exc).__name__}")
            return 3

        request_id = uuid.uuid4().hex
        resp = await client.get(
            "/llm/models",
            params={"view": "mapped"},
            headers={**auth_headers, REQUEST_ID_HEADER: request_id},
            timeout=30.0,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        items = _unwrap_data(payload) or []
        mapped = sorted(
            {
                str(item.get("name") or "").strip()
                for item in items
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            }
        )
        mapped_by_lower = {_normalize_model_key(name): name for name in mapped}

        if not mapped:
            print("FAIL mapped_models_empty")
            return 2

        selected_raw = [str(x).strip() for x in (args.models or []) if str(x).strip()]
        selected = [
            resolved
            for raw in selected_raw
            if (resolved := _resolve_mapped_model_name(raw, mapped_by_lower=mapped_by_lower)) is not None
        ]
        if not selected:
            # 默认优先目标；若不存在再退回全量
            preferred_raw = ["xai", "deepseek"]
            preferred = [
                resolved
                for raw in preferred_raw
                if (resolved := _resolve_mapped_model_name(raw, mapped_by_lower=mapped_by_lower)) is not None
            ]
            selected = preferred or mapped

        missing = [raw for raw in selected_raw if _resolve_mapped_model_name(raw, mapped_by_lower=mapped_by_lower) is None]
        if missing:
            print(f"FAIL mapped_models_missing={','.join(missing)}")
            return 2

        prompt_text = str(args.prompt_text or "").strip()
        turn_texts = _turn_prompts(int(args.turns), first_turn_text=prompt_text or None)

        # App 对外协议：脚本运行期间临时切换，结束后恢复（避免影响其它 E2E/人工调试）。
        original_output_protocol = "thinkingml_v45"
        try:
            request_id = uuid.uuid4().hex
            cfg = await client.get(
                "/llm/app/config",
                headers={**auth_headers, REQUEST_ID_HEADER: request_id},
                timeout=30.0,
            )
            cfg.raise_for_status()
            cfg_data = _unwrap_data(cfg.json()) or {}
            original_output_protocol = (
                str((cfg_data or {}).get("app_output_protocol") or "").strip().lower() or "thinkingml_v45"
            )
        except Exception:
            original_output_protocol = "thinkingml_v45"

        changed_protocol = False
        if output_protocol != original_output_protocol:
            request_id = uuid.uuid4().hex
            updated = await client.post(
                "/llm/app/config",
                headers={**auth_headers, REQUEST_ID_HEADER: request_id},
                json={"app_output_protocol": output_protocol},
                timeout=30.0,
            )
            updated.raise_for_status()
            changed_protocol = True
            if float(args.throttle_seconds) > 0:
                await asyncio.sleep(float(args.throttle_seconds))

        try:
            total = 0
            passed = 0
            failed = 0

            for model in selected:
                for run_index in range(1, int(args.runs) + 1):
                    conversation_id = str(uuid.uuid4())
                    history: list[dict[str, Any]] = []

                    for turn_index, user_text in enumerate(turn_texts, start=1):
                        history.append({"role": "user", "content": user_text})
                        result = await _run_single_turn(
                            client,
                            auth_headers=auth_headers,
                            model=model,
                            app_output_protocol=str(args.app_output_protocol or "thinkingml_v45"),
                            conversation_id=conversation_id,
                            messages=history,
                            tool_choice=str(args.tool_choice or "").strip() or None,
                            temperature=args.temperature,
                            stream_timeout=float(args.stream_timeout),
                            max_events=int(args.max_events),
                            verbose=args.verbose,
                        )
                        total += 1
                        if result.ok:
                            passed += 1
                            print(
                                "PASS "
                                + f"model={model} run={run_index} turn={turn_index} "
                                + f"request_id={result.request_id} message_id={result.message_id} "
                                + f"provider={result.provider} resolved_model={result.resolved_model} endpoint_id={result.endpoint_id} "
                                + f"reply_len={len(result.reply_text)} reason={result.reason}"
                            )
                            history.append({"role": "assistant", "content": result.reply_text})
                            conversation_id = result.conversation_id or conversation_id
                            continue

                        failed += 1
                        print(
                            "FAIL "
                            + f"model={model} run={run_index} turn={turn_index} "
                            + f"request_id={result.request_id} message_id={result.message_id} "
                            + f"provider={result.provider} resolved_model={result.resolved_model} endpoint_id={result.endpoint_id} "
                            + f"reason={result.reason}"
                        )

                        artifact = {
                            "model": model,
                            "run": run_index,
                            "turn": turn_index,
                            "request_id": result.request_id,
                            "message_id": result.message_id,
                            "conversation_id": result.conversation_id,
                            "provider": result.provider,
                            "resolved_model": result.resolved_model,
                            "endpoint_id": result.endpoint_id,
                            "upstream_request_id": result.upstream_request_id,
                            "retried_without_tools": result.retried_without_tools,
                            "reason": result.reason,
                            "sse_error": result.sse_error,
                            "event_counts": result.event_counts,
                            "reply_text": result.reply_text,
                            "prompt_profile_version": profile_version,
                            "tool_choice": str(args.tool_choice or "").strip() or None,
                            "app_output_protocol": output_protocol,
                        }
                        out = artifacts_dir / f"fail_{model}_run{run_index}_turn{turn_index}_{result.request_id}.json"
                        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
                        break

            print(
                f"SUMMARY total={total} passed={passed} failed={failed} models={','.join(selected)} runs={args.runs} turns={args.turns}"
            )
            return 0 if failed == 0 else 3
        finally:
            if changed_protocol:
                try:
                    request_id = uuid.uuid4().hex
                    await client.post(
                        "/llm/app/config",
                        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
                        json={"app_output_protocol": original_output_protocol},
                        timeout=30.0,
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
