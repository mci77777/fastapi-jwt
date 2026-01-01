#!/usr/bin/env python3
"""
每日 E2E（真实用户）：注册(创建) → 登录 → /messages → SSE

目标：每天自动跑一次，验证「真实用户 JWT + 对话链路」无漂移。

实现策略（稳定优先）：
- 使用 Supabase Admin API 创建用户（email_confirm=true），避免依赖邮箱验证码
- 使用 Supabase Public Auth 登录换取 access_token（真实 JWT）
- 调用后端 /api/v1/messages 并消费 SSE，终止于 completed/error
- 产出脱敏 trace JSON（包含 request_id / message_id / SSE 帧摘要），并 stdout 打印 request_id=...

必需环境变量（CI 建议用 Secrets 注入）：
  - E2E_SUPABASE_URL
  - E2E_SUPABASE_ANON_KEY
  - E2E_SUPABASE_SERVICE_ROLE_KEY
  - E2E_API_BASE                 e.g. https://api.gymbro.cloud/api/v1

可选环境变量：
  - E2E_EMAIL_DOMAIN             默认 example.com（如项目限制域名白名单请显式设置）
  - E2E_PROMPT_MODE              server|passthrough（默认 server）
  - E2E_MESSAGE_TEXT             默认 "hello"
  - E2E_OUTPUT_PATH              自定义输出路径（默认 e2e/real_user_sse/artifacts/real_user_signup_trace_<request_id>.json）
  - E2E_CLEANUP_USER             1/true 删除用户（默认 true）

退出码：
  0 通过
  2 环境缺失
  3 运行失败
"""

from __future__ import annotations

import json
import os
import sys
import time
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


def _as_bool(v: str, default: bool = False) -> bool:
    raw = (v or "").strip()
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_output_path(request_id: str) -> Path:
    base = Path("e2e") / "real_user_sse" / "artifacts"
    return base / f"real_user_signup_trace_{request_id}.json"


@dataclass
class SupabaseAdminUser:
    user_id: str
    email: str
    password: str


@dataclass
class SupabaseSession:
    access_token: str
    refresh_token: Optional[str] = None


async def supabase_admin_create_user(
    *,
    supabase_url: str,
    service_role_key: str,
    email: str,
    password: str,
) -> SupabaseAdminUser:
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
        "user_metadata": {"e2e": True, "scenario": "daily_real_user_signup"},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase admin create user failed: HTTP {resp.status_code}")
        data = resp.json()
        user_id = data.get("id") or data.get("user", {}).get("id")
        if not user_id:
            raise RuntimeError("Supabase admin create user 响应缺少 user id")
        return SupabaseAdminUser(user_id=str(user_id), email=email, password=password)


async def supabase_admin_delete_user(
    *,
    supabase_url: str,
    service_role_key: str,
    user_id: str,
) -> None:
    url = supabase_url.rstrip("/") + f"/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase admin delete user failed: HTTP {resp.status_code}")


async def supabase_sign_in_password(
    *,
    supabase_url: str,
    anon_key: str,
    email: str,
    password: str,
) -> SupabaseSession:
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


def _build_message_payload(*, text: str, prompt_mode: str, metadata: dict[str, Any]) -> dict[str, Any]:
    resolved_prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"
    payload: dict[str, Any] = {
        "metadata": {
            "source": "web_ui",
            "timestamp": _iso_now(),
            **(metadata or {}),
        },
        "skip_prompt": (resolved_prompt_mode == "passthrough"),
    }
    if text.strip():
        payload["text"] = text.strip()
    else:
        raise RuntimeError("E2E_MESSAGE_TEXT 不能为空")
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
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream", "X-Request-Id": request_id}

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
                        if evt.get("event") in ("completed", "error"):
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


async def main() -> int:
    try:
        supabase_url = _require_env("E2E_SUPABASE_URL")
        supabase_anon_key = _require_env("E2E_SUPABASE_ANON_KEY")
        service_role_key = _require_env("E2E_SUPABASE_SERVICE_ROLE_KEY")
        api_base = _require_env("E2E_API_BASE")
    except KeyError as e:
        sys.stderr.write(f"Missing env: {e}\n")
        return 2

    email_domain = (os.getenv("E2E_EMAIL_DOMAIN") or "example.com").strip()
    prompt_mode = (os.getenv("E2E_PROMPT_MODE") or "server").strip().lower()
    prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"
    text = (os.getenv("E2E_MESSAGE_TEXT") or "hello").strip()
    cleanup_user = _as_bool(os.getenv("E2E_CLEANUP_USER") or "", default=True)

    request_id = str(uuid.uuid4())
    report = TraceReport(
        request_id=request_id,
        context={
            "api_base": api_base,
            "prompt_mode": prompt_mode,
            "supabase_url": supabase_url,
            "email_domain": email_domain,
        },
    )
    logger = TraceLogger(report, verbose=True)

    output_path_raw = (os.getenv("E2E_OUTPUT_PATH") or "").strip()
    output_path = Path(output_path_raw) if output_path_raw else _default_output_path(request_id)

    created_user: Optional[SupabaseAdminUser] = None
    try:
        # 1) 注册（创建）用户
        ts = int(time.time())
        email = f"e2e_{ts}_{request_id[:8]}@{email_domain}"
        password = f"E2E!{request_id.replace('-', '')[:16]}"

        t0 = time.time()
        created_user = await supabase_admin_create_user(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            email=email,
            password=password,
        )
        t1 = time.time()
        logger.step(
            "supabase_admin_create_user",
            ok=True,
            started_at=t0,
            finished_at=t1,
            request={"url": f"{supabase_url.rstrip('/')}/auth/v1/admin/users", "headers": {"apikey": "<redacted>"}, "body": {"email": email, "password": "<redacted>"}},
            response={"user_id": created_user.user_id},
        )

        # 2) 登录拿 JWT
        t2 = time.time()
        session = await supabase_sign_in_password(
            supabase_url=supabase_url,
            anon_key=supabase_anon_key,
            email=email,
            password=password,
        )
        t3 = time.time()
        logger.step(
            "supabase_sign_in_password",
            ok=True,
            started_at=t2,
            finished_at=t3,
            request={"url": f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password", "headers": {"apikey": "<redacted>"}, "body": {"email": email, "password": "<redacted>"}},
            response={"has_access_token": bool(session.access_token), "has_refresh_token": bool(session.refresh_token)},
        )

        # 3) 对话（create → SSE）
        payload = _build_message_payload(
            text=text,
            prompt_mode=prompt_mode,
            metadata={"e2e": True, "scenario": "daily_real_user_signup_login_sse"},
        )

        t4 = time.time()
        message_id, conversation_id = await create_message(
            api_base=api_base,
            token=session.access_token,
            request_id=request_id,
            payload=payload,
        )
        t5 = time.time()
        logger.step(
            "create_message",
            ok=True,
            started_at=t4,
            finished_at=t5,
            request={"url": f"{api_base.rstrip('/')}/messages", "headers": {"X-Request-Id": request_id}, "body": payload},
            response={"message_id": message_id, "conversation_id": conversation_id},
        )

        t6 = time.time()
        sse_result = await consume_sse(
            api_base=api_base,
            token=session.access_token,
            request_id=request_id,
            message_id=message_id,
            conversation_id=conversation_id,
        )
        t7 = time.time()
        final_evt = sse_result["final"]
        logger.step(
            "consume_sse",
            ok=True,
            started_at=t6,
            finished_at=t7,
            request={"url": f"{api_base.rstrip('/')}/messages/{message_id}/events", "headers": {"X-Request-Id": request_id}},
            response={"final_event": final_evt.get("event"), "seen": sse_result.get("seen")},
            notes={"frames": sse_result.get("frames", [])},
        )

        # 4) 校验 request_id 对账
        if final_evt.get("event") == "error":
            data = final_evt.get("data")
            if isinstance(data, dict) and data.get("request_id") != request_id:
                raise RuntimeError("SSE error 的 request_id 与 create 的 X-Request-Id 不一致")
            raise RuntimeError("SSE 返回 error（已校验 request_id）")

        if final_evt.get("event") != "completed":
            raise RuntimeError(f"未预期的终止事件：{final_evt.get('event')}")

        data = final_evt.get("data")
        if isinstance(data, dict):
            rid = data.get("request_id")
            if rid and rid != request_id:
                raise RuntimeError("SSE completed 的 request_id 与 create 的 X-Request-Id 不一致")

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
    finally:
        if created_user and cleanup_user:
            try:
                t8 = time.time()
                await supabase_admin_delete_user(
                    supabase_url=supabase_url,
                    service_role_key=service_role_key,
                    user_id=created_user.user_id,
                )
                t9 = time.time()
                logger.step(
                    "supabase_admin_delete_user",
                    ok=True,
                    started_at=t8,
                    finished_at=t9,
                    request={"url": f"{supabase_url.rstrip('/')}/auth/v1/admin/users/{created_user.user_id}", "headers": {"apikey": "<redacted>"}},
                    response={},
                )
                report.finished_at = report.finished_at or time.time()
                report.write_json(output_path)
            except Exception:
                # 不影响主流程退出码
                pass


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))

