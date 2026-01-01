#!/usr/bin/env python3
"""
真实用户 E2E：Supabase（密码登录）→ 后端 /messages → SSE（完成或错误）

不做 mock；需要你提供真实用户凭证与 Supabase anon key（通过环境变量传入）。

必需环境变量：
  - E2E_SUPABASE_URL          e.g. https://<project>.supabase.co
  - E2E_SUPABASE_ANON_KEY     Supabase anon key（前端可公开，但不要写入仓库）
  - E2E_USER_EMAIL            真实用户 email
  - E2E_USER_PASSWORD         真实用户 password

可选环境变量：
  - E2E_API_BASE              默认 http://127.0.0.1:9999/api/v1
  - E2E_MESSAGE_TEXT          默认 "hello"
  - E2E_OPENAI_MODEL          可选：透传 model
  - E2E_OPENAI_MESSAGES_JSON  可选：OpenAI messages（JSON 字符串）
  - E2E_SYSTEM_PROMPT         可选：system prompt（仅 passthrough 生效）
  - E2E_TOOLS_JSON            可选：tools（JSON 字符串）
  - E2E_TOOL_CHOICE_JSON      可选：tool_choice（JSON 字符串）
  - E2E_TEMPERATURE           可选：temperature（float）
  - E2E_TOP_P                 可选：top_p（float）
  - E2E_MAX_TOKENS            可选：max_tokens（int）
  - E2E_PROMPT_MODE           server|passthrough（默认 server）
  - E2E_OUTPUT_PATH           可选：trace 输出路径（默认 e2e/real_user_sse/artifacts/real_user_sse_trace_<request_id>.json）
  - E2E_VERIFY_SQLITE         可选：1/true 时校验 db.sqlite3 已写入 request_id（本地模式）

退出码：
  0 通过
  2 环境缺失
  3 运行失败
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from scripts.monitoring.e2e_trace import TraceLogger, TraceReport, _safe_sse_event


def _require_env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise KeyError(name)
    return v


def _as_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _parse_json_env(name: str) -> Any:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    return json.loads(raw)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SupabaseSession:
    access_token: str
    refresh_token: Optional[str] = None


async def supabase_sign_in_password(*, supabase_url: str, anon_key: str, email: str, password: str) -> SupabaseSession:
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
            raise RuntimeError(f"Supabase 登录失败：HTTP {resp.status_code}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Supabase 登录响应缺少 access_token")
        return SupabaseSession(access_token=token, refresh_token=data.get("refresh_token"))


def _build_message_payload(
    *,
    text: str,
    conversation_id: Optional[str],
    prompt_mode: str,
    openai: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    对齐 Web `web/src/api/aiModelSuite.js::createMessage` 的最小构建逻辑：
    - text / messages 二选一（至少一个）
    - metadata 默认包含 source/timestamp
    - server 模式过滤 system role；passthrough 才允许 system_prompt
    """
    has_text = isinstance(text, str) and bool(text.strip())
    messages = openai.get("messages")
    has_messages = isinstance(messages, list) and len(messages) > 0
    if not has_text and not has_messages:
        raise RuntimeError("text 或 openai.messages 至少提供一个")

    resolved_prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"

    payload: dict[str, Any] = {
        "conversation_id": conversation_id or None,
        "metadata": {
            "source": "web_ui",
            "timestamp": _iso_now(),
            **(metadata or {}),
        },
    }

    if has_text:
        payload["text"] = text.strip()

    payload["skip_prompt"] = resolved_prompt_mode == "passthrough"

    model = openai.get("model")
    if isinstance(model, str) and model.strip():
        payload["model"] = model.strip()

    system_prompt = openai.get("system_prompt")
    if isinstance(system_prompt, str) and system_prompt.strip():
        if resolved_prompt_mode == "passthrough":
            payload["system_prompt"] = system_prompt.strip()

    if has_messages:
        if resolved_prompt_mode == "server":
            payload["messages"] = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
        else:
            payload["messages"] = [m for m in messages if isinstance(m, dict)]

    for key in ("tools", "tool_choice", "temperature", "top_p", "max_tokens"):
        if key in openai and openai[key] is not None:
            payload[key] = openai[key]

    return payload


async def create_message(*, api_base: str, token: str, request_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    url = api_base.rstrip("/") + "/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Request-Id": request_id}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 202:
            raise RuntimeError(f"/messages 创建失败：HTTP {resp.status_code}")
        data = resp.json()
        mid = data.get("message_id")
        cid = data.get("conversation_id")
        if not mid or not cid:
            raise RuntimeError("/messages 响应缺少 message_id/conversation_id")
        return str(mid), str(cid)


async def consume_sse(
    *,
    api_base: str,
    token: str,
    request_id: str,
    message_id: str,
    conversation_id: str,
    max_events: int = 5000,
) -> dict[str, Any]:
    base_url = httpx.URL(api_base.rstrip("/") + f"/messages/{message_id}/events")
    url = str(base_url.copy_merge_params({"conversation_id": conversation_id}))
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "X-Request-Id": request_id,
    }

    current_event: str = "message"
    data_lines: list[str] = []
    seen = 0
    reply_accum = ""
    frames: list[dict[str, Any]] = []

    async def flush() -> Optional[dict[str, Any]]:
        nonlocal data_lines, current_event
        if not data_lines:
            return None
        raw = "\n".join(data_lines)
        data_lines = []
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return {"event": current_event or "message", "data": parsed}

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"SSE 连接失败：HTTP {resp.status_code}")

            async for line in resp.aiter_lines():
                if line is None:
                    continue
                line = line.rstrip("\r")
                if line == "":
                    evt = await flush()
                    if evt:
                        seen += 1
                        frames.append(_safe_sse_event(str(evt.get("event")), evt.get("data")))
                        if evt.get("event") == "content_delta":
                            data = evt.get("data")
                            if isinstance(data, dict) and data.get("delta"):
                                reply_accum += str(data.get("delta"))
                        if evt["event"] in ("completed", "error"):
                            return {"final": evt, "frames": frames, "reply_accum": reply_accum, "seen": seen}
                        if seen >= max_events:
                            raise RuntimeError("SSE 事件数量超限，可能未正常结束")
                    current_event = "message"
                    continue
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())

    raise RuntimeError("SSE 提前结束（未收到 completed/error）")


def _default_output_path(request_id: str) -> Path:
    base = Path("e2e") / "real_user_sse" / "artifacts"
    return base / f"real_user_sse_trace_{request_id}.json"


def _verify_sqlite_written(message_id: str, request_id: str) -> None:
    """
    本地对齐校验：确认后端已把 request_id 写入 sqlite conversation_logs.response_payload.sse.request_id。

    注意：该校验仅适用于本仓库默认 sqlite（db.sqlite3）模式。
    """
    import sqlite3

    db_path = Path("db.sqlite3")
    if not db_path.exists():
        raise RuntimeError("db.sqlite3 不存在，无法做 sqlite 写入校验")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT response_payload
            FROM conversation_logs
            WHERE message_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("sqlite 未找到对应 message_id 的 conversation_logs 记录")
        raw = row[0] or ""
        payload = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
        sse = payload.get("sse") if isinstance(payload, dict) else None
        rid = sse.get("request_id") if isinstance(sse, dict) else None
        if rid != request_id:
            raise RuntimeError("sqlite response_payload.sse.request_id 与 create 的 X-Request-Id 不一致")
    finally:
        conn.close()


async def main() -> int:
    try:
        supabase_url = _require_env("E2E_SUPABASE_URL")
        supabase_anon_key = _require_env("E2E_SUPABASE_ANON_KEY")
        email = _require_env("E2E_USER_EMAIL")
        password = _require_env("E2E_USER_PASSWORD")
    except KeyError as e:
        sys.stderr.write(f"Missing env: {e}\n")
        return 2

    api_base = (os.getenv("E2E_API_BASE") or "http://127.0.0.1:9999/api/v1").strip()
    text = (os.getenv("E2E_MESSAGE_TEXT") or "hello").strip()
    prompt_mode = (os.getenv("E2E_PROMPT_MODE") or "server").strip().lower()
    prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"
    verify_sqlite = _as_bool(os.getenv("E2E_VERIFY_SQLITE") or "false")

    openai: dict[str, Any] = {}
    openai_model = (os.getenv("E2E_OPENAI_MODEL") or "").strip()
    if openai_model:
        openai["model"] = openai_model

    messages = _parse_json_env("E2E_OPENAI_MESSAGES_JSON")
    if messages is not None:
        openai["messages"] = messages

    system_prompt = (os.getenv("E2E_SYSTEM_PROMPT") or "").strip()
    if system_prompt:
        openai["system_prompt"] = system_prompt

    tools = _parse_json_env("E2E_TOOLS_JSON")
    if tools is not None:
        openai["tools"] = tools

    tool_choice = _parse_json_env("E2E_TOOL_CHOICE_JSON")
    if tool_choice is not None:
        openai["tool_choice"] = tool_choice

    temperature = (os.getenv("E2E_TEMPERATURE") or "").strip()
    if temperature:
        openai["temperature"] = float(temperature)

    top_p = (os.getenv("E2E_TOP_P") or "").strip()
    if top_p:
        openai["top_p"] = float(top_p)

    max_tokens = (os.getenv("E2E_MAX_TOKENS") or "").strip()
    if max_tokens:
        openai["max_tokens"] = int(max_tokens)

    conversation_id = (os.getenv("E2E_CONVERSATION_ID") or "").strip() or None

    request_id = str(uuid.uuid4())
    report = TraceReport(
        request_id=request_id,
        context={
            "api_base": api_base,
            "prompt_mode": prompt_mode,
            "supabase_url": supabase_url,
            "user_email": email,
        },
    )
    logger = TraceLogger(report, verbose=True)

    output_path_raw = (os.getenv("E2E_OUTPUT_PATH") or "").strip()
    output_path = Path(output_path_raw) if output_path_raw else _default_output_path(request_id)

    try:
        t0 = time.time()
        session = await supabase_sign_in_password(supabase_url=supabase_url, anon_key=supabase_anon_key, email=email, password=password)
        t1 = time.time()
        logger.step(
            "supabase_sign_in_password",
            ok=True,
            started_at=t0,
            finished_at=t1,
            request={"url": f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password", "headers": {"apikey": supabase_anon_key}, "body": {"email": email, "password": "<redacted>"}},
            response={"has_access_token": bool(session.access_token), "has_refresh_token": bool(session.refresh_token)},
        )

        payload = _build_message_payload(
            text=text,
            conversation_id=conversation_id,
            prompt_mode=prompt_mode,
            openai=openai,
            metadata={"e2e": True, "scenario": "real_user_sse_e2e"},
        )

        t2 = time.time()
        message_id, conv_id = await create_message(api_base=api_base, token=session.access_token, request_id=request_id, payload=payload)
        t3 = time.time()
        logger.step(
            "create_message",
            ok=True,
            started_at=t2,
            finished_at=t3,
            request={"url": f"{api_base.rstrip('/')}/messages", "headers": {"X-Request-Id": request_id}, "body": payload},
            response={"message_id": message_id, "conversation_id": conv_id},
        )

        logger.log(f"message_id={message_id} conversation_id={conv_id}")

        t4 = time.time()
        sse_result = await consume_sse(
            api_base=api_base,
            token=session.access_token,
            request_id=request_id,
            message_id=message_id,
            conversation_id=conv_id,
        )
        t5 = time.time()
        final_evt = sse_result["final"]
        logger.step(
            "consume_sse",
            ok=True,
            started_at=t4,
            finished_at=t5,
            request={"url": f"{api_base.rstrip('/')}/messages/{message_id}/events", "headers": {"X-Request-Id": request_id}},
            response={"final_event": final_evt.get("event"), "seen": sse_result.get("seen")},
            notes={"frames": sse_result.get("frames", [])},
        )

        if final_evt.get("event") == "error":
            data = final_evt.get("data")
            if isinstance(data, dict):
                rid = data.get("request_id")
                if rid != request_id:
                    raise RuntimeError("SSE error 的 request_id 与 create 的 X-Request-Id 不一致")
            raise RuntimeError("SSE 返回 error（已校验 request_id）")

        if final_evt.get("event") != "completed":
            raise RuntimeError(f"未预期的终止事件：{final_evt.get('event')}")

        data = final_evt.get("data")
        if isinstance(data, dict):
            rid = data.get("request_id")
            if rid and rid != request_id:
                raise RuntimeError("SSE completed 的 request_id 与 create 的 X-Request-Id 不一致")

        if verify_sqlite:
            _verify_sqlite_written(message_id, request_id)
            logger.log("sqlite_verify=ok")

        report.finished_at = time.time()
        report.write_json(output_path)
        logger.log(f"trace_written={output_path}")
        return 0
    except Exception as exc:
        report.finished_at = time.time()
        try:
            report.context["error"] = str(exc)
            report.write_json(output_path)
            logger.log(f"trace_written={output_path} error=1")
        except Exception:
            pass
        sys.stderr.write(f"request_id={request_id} E2E failed: {exc}\n")
        return 3


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
