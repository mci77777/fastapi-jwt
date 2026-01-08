#!/usr/bin/env python3
"""
真实用户 JWT E2E（Supabase）+ ThinkingML 结构校验：

1) （可选）Dashboard admin 登录（/api/v1/base/access_token）→ 写入并 activate prompts（SSOT：assets/prompts/*）
2) 获取真实用户 JWT（Supabase password 登录，或 service role 创建用户后再登录）
3) JWT 负例：无 Authorization / 无效 token → 401 + 结构化 error
4) 逐 mapping 发起多轮对话：POST /messages → SSE /events 拼接 reply → 校验 ThinkingML（SSOT：docs/ai预期响应结构.md）

退出码：
  0 通过
  2 前置条件缺失（Supabase/服务不可用/模型未配置）
  3 运行失败（任一轮次 FAIL）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# 复用同一份契约校验器（SSOT：local_mock_ai_conversation_e2e.py）
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.monitoring.local_mock_ai_conversation_e2e import (  # noqa: E402
    _load_prompt_assets,
    _parse_tools_from_tool_md,
    _validate_thinkingml,
)


REQUEST_ID_HEADER = "X-Request-Id"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def _normalize_api_base(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:9999/api/v1"
    text = text.rstrip("/")
    if text.endswith("/api/v1"):
        return text
    return text + "/api/v1"


def _print(msg: str, *, verbose: bool) -> None:
    if verbose:
        print(msg)


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def _load_env_file(path: Path, *, override: bool) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not key or " " in key:
            continue
        val = val.strip()
        if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
            val = val[1:-1]
        if override:
            os.environ[key] = val
        else:
            os.environ.setdefault(key, val)


def _load_env_defaults() -> None:
    # 先加载根目录 .env，再加载 e2e/anon_jwt_sse/.env.local 覆盖（若存在）
    _load_env_file(REPO_ROOT / ".env", override=False)
    _load_env_file(REPO_ROOT / "e2e" / "anon_jwt_sse" / ".env.local", override=True)


async def _dashboard_login(client: httpx.AsyncClient, *, username: str, password: str, verbose: bool) -> str:
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


@dataclass
class SupabaseUser:
    user_id: str
    email: str
    password: str


async def _supabase_sign_in_password(*, supabase_url: str, anon_key: str, email: str, password: str) -> str:
    url = supabase_url.rstrip("/") + "/auth/v1/token?grant_type=password"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }
    payload = {"email": email, "password": password}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            detail = ""
            try:
                data = resp.json()
                detail = (
                    data.get("msg")
                    or data.get("message")
                    or data.get("error_description")
                    or data.get("error")
                    or ""
                )
            except Exception:
                detail = ""
            detail = (str(detail).strip() if detail is not None else "").strip()
            suffix = f" ({detail})" if detail else ""
            raise RuntimeError(f"supabase_sign_in_failed: HTTP {resp.status_code}{suffix}")
        data = resp.json() or {}
        token = str(data.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("supabase_login_missing_access_token")
        return token


async def _supabase_admin_create_user(
    *,
    supabase_url: str,
    service_role_key: str,
    email: str,
    password: str,
) -> SupabaseUser:
    url = supabase_url.rstrip("/") + "/auth/v1/admin/users"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"e2e": True, "scenario": "real_user_ai_conversation_e2e"},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"supabase_admin_create_user_failed: HTTP {resp.status_code}")
        data = resp.json() or {}
        user_id = data.get("id") or (data.get("user") or {}).get("id")
        if not user_id:
            raise RuntimeError("supabase_admin_create_user_missing_id")
        return SupabaseUser(user_id=str(user_id), email=email, password=password)


async def _supabase_admin_delete_user(*, supabase_url: str, service_role_key: str, user_id: str) -> None:
    url = supabase_url.rstrip("/") + f"/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"supabase_admin_delete_user_failed: HTTP {resp.status_code}")


async def _jwt_negative_tests(client: httpx.AsyncClient, *, verbose: bool) -> tuple[int, int]:
    total = 0
    passed = 0

    async def check(name: str, method: str, url: str, *, headers: dict[str, str] | None, json_body: Any | None, want_status: int, want_code: str) -> None:
        nonlocal total, passed
        total += 1
        request_id = uuid.uuid4().hex
        send_headers = {"Content-Type": "application/json", REQUEST_ID_HEADER: request_id}
        if headers:
            send_headers.update(headers)
        resp = await client.request(method, url, headers=send_headers, json=json_body, timeout=30.0)
        ok = resp.status_code == want_status
        code = ""
        try:
            payload = resp.json()
            code = str((payload or {}).get("code") or "")
        except Exception:
            code = ""
        ok = ok and code == want_code
        if ok:
            passed += 1
            print(f"PASS jwt={name} status={resp.status_code} code={code} request_id={request_id}")
        else:
            body = (resp.text or "")[:240]
            print(f"FAIL jwt={name} status={resp.status_code} code={code} want_status={want_status} want_code={want_code} request_id={request_id} body={body}")
        _print(f"[jwt] {name} request_id={request_id}", verbose=verbose)

    await check(
        "messages_no_auth",
        "POST",
        "/messages",
        headers=None,
        json_body={"text": "hi"},
        want_status=401,
        want_code="unauthorized",
    )
    await check(
        "messages_bad_token",
        "POST",
        "/messages",
        headers={"Authorization": "Bearer invalid"},
        json_body={"text": "hi"},
        want_status=401,
        want_code="invalid_token_header",
    )
    await check(
        "models_no_auth",
        "GET",
        "/llm/models?view=mapped",
        headers=None,
        json_body=None,
        want_status=401,
        want_code="unauthorized",
    )

    return total, passed


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
    conversation_id: str,
    messages: list[dict[str, Any]],
    tool_choice: str | None,
    temperature: float | None,
    stream_timeout: float,
    max_events: int,
    throttle_seconds: float,
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
        if throttle_seconds > 0:
            await asyncio.sleep(throttle_seconds)
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
            meta, _, reply_text, sse_error, event_counts = await send(tool_choice_value=None)
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
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        body = (exc.response.text or "") if exc.response is not None else ""
        body = body[:240]
        return TurnResult(
            ok=False,
            reason=f"exception:HTTPStatusError:{status}",
            request_id=request_id,
            message_id="",
            conversation_id=conversation_id,
            provider=None,
            resolved_model=None,
            endpoint_id=None,
            upstream_request_id=None,
            reply_text=body,
            retried_without_tools=False,
            sse_error=None,
            event_counts={},
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


def _turn_prompts(turns: int) -> list[str]:
    base = [
        "给我一份三分化训练方案，适合新手，包含动作与每周频率。",
        "请把每次训练的热身与收操补齐，并把总时长控制在 60 分钟内。",
        "用 RPE 给出强度建议，并说明如何做渐进超负荷。",
    ]
    if turns <= len(base):
        return base[:turns]
    more = [f"把第 {i+1} 轮建议进一步量化（组数/次数/休息）。" for i in range(len(base), turns)]
    return base + more


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real user JWT E2E (Supabase) + ThinkingML contract")
    parser.add_argument("--api-base", default=os.getenv("E2E_API_BASE", "http://127.0.0.1:9999/api/v1"))
    parser.add_argument("--models", nargs="*", default=None, help="映射名列表（如 xai deepseek）；不传则跑全部 mapped models")
    parser.add_argument("--runs", type=int, default=_as_int(os.getenv("E2E_RUNS"), 1))
    parser.add_argument("--turns", type=int, default=_as_int(os.getenv("E2E_TURNS"), 1))
    parser.add_argument(
        "--tool-choice",
        default=os.getenv("E2E_TOOL_CHOICE", "none"),
        help="OpenAI tool_choice：auto/none/required。默认 none；传空字符串表示不下发该字段。",
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=float(os.getenv("E2E_THROTTLE_SECONDS", "0.35")),
        help="为避免 IP QPS 限流，对初始化/每轮请求做节流（单位：秒）。",
    )
    parser.add_argument("--stream-timeout", type=float, default=float(os.getenv("E2E_STREAM_TIMEOUT", "180")))
    parser.add_argument("--max-events", type=int, default=_as_int(os.getenv("E2E_MAX_EVENTS", 4000), 4000))
    parser.add_argument("--artifacts-dir", default=os.getenv("E2E_ARTIFACTS_DIR", "e2e/real_user_ai_conversation/artifacts"))
    parser.add_argument("--verbose", action="store_true", default=str(os.getenv("E2E_VERBOSE", "1")).strip().lower() in ("1", "true", "yes"))

    parser.add_argument("--setup-prompts", action="store_true", default=_as_bool(os.getenv("E2E_SETUP_PROMPTS", "1"), True))
    parser.add_argument("--dashboard-username", default=os.getenv("E2E_ADMIN_USERNAME", "admin"))
    parser.add_argument("--dashboard-password", default=os.getenv("E2E_ADMIN_PASSWORD", "123456"))

    parser.add_argument("--auth-mode", choices=["password", "signup"], default=os.getenv("E2E_AUTH_MODE", "password"))
    parser.add_argument("--email-domain", default=os.getenv("E2E_EMAIL_DOMAIN", "example.com"))
    return parser.parse_args()


async def main() -> int:
    _load_env_defaults()

    args = _parse_args()
    api_base = _normalize_api_base(args.api_base)
    artifacts_dir = (REPO_ROOT / str(args.artifacts_dir)).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / ".gitkeep").write_text("", encoding="utf-8")

    profile, serp_prompt, tool_prompt = _load_prompt_assets()
    tools_schema = _parse_tools_from_tool_md(tool_prompt)
    profile_version = str((profile or {}).get("version") or "").strip() or "v1"

    supabase_url = str(os.getenv("E2E_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").strip()
    supabase_anon_key = str(os.getenv("E2E_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
    supabase_service_role_key = str(
        os.getenv("E2E_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    ).strip()

    created_user: SupabaseUser | None = None
    cleanup_user = True

    try:
        async with httpx.AsyncClient(base_url=api_base) as client:
            # 0) prompt SSOT（需要 admin 权限）
            if bool(args.setup_prompts):
                try:
                    admin_token = await _dashboard_login(
                        client,
                        username=args.dashboard_username,
                        password=args.dashboard_password,
                        verbose=args.verbose,
                    )
                    admin_headers = {"Authorization": f"Bearer {admin_token}"}
                    await _ensure_prompt(
                        client,
                        auth_headers=admin_headers,
                        name="SSOT:standard_serp_system",
                        prompt_type="system",
                        content=serp_prompt,
                        version=profile_version,
                        category="ssot",
                        description="Strict XML / ThinkingML v4.5 system prompt (serp)",
                        tools_json=None,
                        throttle_seconds=float(args.throttle_seconds),
                        verbose=args.verbose,
                    )
                    await _ensure_prompt(
                        client,
                        auth_headers=admin_headers,
                        name="SSOT:standard_serp_tools",
                        prompt_type="tools",
                        content=tool_prompt,
                        version=profile_version,
                        category="ssot",
                        description="ToolCall patch (does not change Strict XML output protocol)",
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

            # 1) 获取真实用户 JWT
            if not supabase_url or not supabase_anon_key:
                print("FAIL missing_supabase_env (need SUPABASE_URL + SUPABASE_ANON_KEY)")
                return 2

            token: str | None = None
            try:
                if args.auth_mode == "signup":
                    if not supabase_service_role_key:
                        print("FAIL missing_supabase_service_role_key (need SUPABASE_SERVICE_ROLE_KEY for signup mode)")
                        return 2
                    email_domain = str(args.email_domain or "example.com").strip() or "example.com"
                    email = f"e2e_{uuid.uuid4().hex[:10]}@{email_domain}"
                    password = "E2E!" + secrets.token_urlsafe(18)
                    created_user = await _supabase_admin_create_user(
                        supabase_url=supabase_url,
                        service_role_key=supabase_service_role_key,
                        email=email,
                        password=password,
                    )
                    token = await _supabase_sign_in_password(
                        supabase_url=supabase_url,
                        anon_key=supabase_anon_key,
                        email=created_user.email,
                        password=created_user.password,
                    )
                else:
                    email = str(os.getenv("E2E_USER_EMAIL") or os.getenv("TEST_USER_EMAIL") or "").strip()
                    password = str(os.getenv("E2E_USER_PASSWORD") or os.getenv("TEST_USER_PASSWORD") or "").strip()
                    if not email or not password:
                        print(
                            "FAIL missing_user_credentials (need TEST_USER_EMAIL/TEST_USER_PASSWORD or E2E_USER_EMAIL/E2E_USER_PASSWORD)"
                        )
                        return 2
                    token = await _supabase_sign_in_password(
                        supabase_url=supabase_url,
                        anon_key=supabase_anon_key,
                        email=email,
                        password=password,
                    )
            except Exception as exc:
                print(f"FAIL supabase_login reason={type(exc).__name__}")
                return 2

            assert token
            auth_headers = {"Authorization": f"Bearer {token}"}

            # 2) JWT 负例测试
            jwt_total, jwt_passed = await _jwt_negative_tests(client, verbose=args.verbose)
            print(f"SUMMARY_JWT total={jwt_total} passed={jwt_passed} failed={jwt_total - jwt_passed}")
            if jwt_passed != jwt_total:
                return 3

            # 3) 获取 mapped models（SSOT）
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
            if not mapped:
                print("FAIL mapped_models_empty")
                return 2

            selected = [str(x).strip() for x in (args.models or []) if str(x).strip()]
            if not selected:
                preferred = [x for x in ("xai", "deepseek") if x in mapped]
                selected = preferred or mapped

            missing = [m for m in selected if m not in mapped]
            if missing:
                print(f"FAIL mapped_models_missing={','.join(missing)}")
                return 2

            # 4) 多轮对话（真实 SSE + 结构校验）
            turn_texts = _turn_prompts(int(args.turns))
            total = 0
            passed = 0
            failed = 0

            for model in selected:
                for run_index in range(1, int(args.runs) + 1):
                    conversation_id = str(uuid.uuid4())
                    history: list[dict[str, Any]] = []

                    for turn_index, user_text in enumerate(turn_texts, start=1):
                        history.append({"role": "user", "content": user_text})
                        tool_choice_value = str(args.tool_choice or "").strip() or None
                        result = await _run_single_turn(
                            client,
                            auth_headers=auth_headers,
                            model=model,
                            conversation_id=conversation_id,
                            messages=history,
                            tool_choice=tool_choice_value,
                            temperature=args.temperature,
                            stream_timeout=float(args.stream_timeout),
                            max_events=int(args.max_events),
                            throttle_seconds=float(args.throttle_seconds),
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
                            "tool_choice": tool_choice_value,
                            "auth_mode": str(args.auth_mode),
                        }
                        out = artifacts_dir / f"fail_{model}_run{run_index}_turn{turn_index}_{result.request_id}.json"
                        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
                        break

            print(
                f"SUMMARY total={total} passed={passed} failed={failed} "
                + f"models={','.join(selected)} runs={args.runs} turns={args.turns} auth_mode={args.auth_mode}"
            )
            return 0 if failed == 0 else 3
    finally:
        if created_user and cleanup_user and supabase_service_role_key and supabase_url:
            try:
                await _supabase_admin_delete_user(
                    supabase_url=supabase_url,
                    service_role_key=supabase_service_role_key,
                    user_id=created_user.user_id,
                )
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
