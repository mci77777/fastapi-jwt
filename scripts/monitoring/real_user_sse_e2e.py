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
  - E2E_PROMPT_MODE           server|passthrough（默认 server）

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
from typing import Any, Optional

import httpx


def _require_env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise KeyError(name)
    return v


def _as_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


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


async def create_message(
    *,
    api_base: str,
    token: str,
    request_id: str,
    text: str,
    prompt_mode: str,
    openai_model: Optional[str],
) -> tuple[str, str]:
    url = api_base.rstrip("/") + "/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }
    payload: dict[str, Any] = {
        "metadata": {"source": "e2e_real_user", "e2e": True},
        "skip_prompt": (prompt_mode == "passthrough"),
    }
    if text.strip():
        payload["text"] = text.strip()
    if openai_model:
        payload["model"] = openai_model

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
                        if evt["event"] in ("completed", "error"):
                            return evt
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
        email = _require_env("E2E_USER_EMAIL")
        password = _require_env("E2E_USER_PASSWORD")
    except KeyError as e:
        sys.stderr.write(f"Missing env: {e}\n")
        return 2

    api_base = (os.getenv("E2E_API_BASE") or "http://127.0.0.1:9999/api/v1").strip()
    text = (os.getenv("E2E_MESSAGE_TEXT") or "hello").strip()
    prompt_mode = (os.getenv("E2E_PROMPT_MODE") or "server").strip().lower()
    prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"
    openai_model = (os.getenv("E2E_OPENAI_MODEL") or "").strip() or None

    request_id = str(uuid.uuid4())

    try:
        session = await supabase_sign_in_password(
            supabase_url=supabase_url,
            anon_key=supabase_anon_key,
            email=email,
            password=password,
        )
        message_id, conversation_id = await create_message(
            api_base=api_base,
            token=session.access_token,
            request_id=request_id,
            text=text,
            prompt_mode=prompt_mode,
            openai_model=openai_model,
        )
        final_evt = await consume_sse(
            api_base=api_base,
            token=session.access_token,
            request_id=request_id,
            message_id=message_id,
            conversation_id=conversation_id,
        )

        if final_evt["event"] == "error":
            data = final_evt.get("data")
            if isinstance(data, dict):
                rid = data.get("request_id")
                if rid != request_id:
                    raise RuntimeError("SSE error 的 request_id 与 create 的 X-Request-Id 不一致")
            raise RuntimeError("SSE 返回 error（已校验 request_id）")

        if final_evt["event"] != "completed":
            raise RuntimeError(f"未预期的终止事件：{final_evt['event']}")

        data = final_evt.get("data")
        if isinstance(data, dict):
            rid = data.get("request_id")
            if rid and rid != request_id:
                raise RuntimeError("SSE completed 的 request_id 与 create 的 X-Request-Id 不一致")

        return 0
    except Exception as exc:
        sys.stderr.write(f"E2E failed: {exc}\n")
        return 3


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
