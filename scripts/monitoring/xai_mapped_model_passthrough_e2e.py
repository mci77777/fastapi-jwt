#!/usr/bin/env python3
"""
xAI E2E（不做 mock）：
1) Dashboard 本地 admin 登录（/api/v1/base/access_token）获取 JWT
2) upsert xAI endpoint（OpenAI-compat）：base_url + api_key + provider_model
3) upsert 映射模型：global:xai -> grok-4.1-思考（可通过 env 覆盖）
4) 使用 assets/prompts 组装并激活 system/tools prompt
5) 发起两次对话：
   - server 模式（不透传）：后端注入 system/tools
   - passthrough 模式（透传）：客户端完全提供 system/messages/tools
6) 消费 SSE，校验：
   - routed 事件回传 provider=xai 且 resolved_model=provider_model
   - completed.reply 满足 docs/ai预期响应结构.md（ThinkingML v4.5 XML）

必需环境变量：
  - XAI_API_KEY                 xAI API Key（不要写入仓库）

可选环境变量：
  - E2E_API_BASE                默认 http://127.0.0.1:9999/api/v1
  - E2E_ADMIN_USERNAME          默认 admin
  - E2E_ADMIN_PASSWORD          默认 123456
  - XAI_API_BASE_URL            默认 https://api.x.ai
  - XAI_PROVIDER_MODEL          默认 grok-4.1-思考
  - E2E_MAPPED_MODEL_KEY        默认 global:xai（即 scope_type=global scope_key=xai）
  - E2E_MESSAGE_TEXT            默认 给我一份三分化训练方案
  - E2E_OUTPUT_PATH             默认 e2e/real_user_sse/artifacts/xai_mapped_model_trace_<request_id>.json
  - E2E_VERBOSE                 1/true 打印步骤日志（默认 true）

退出码：
  0 通过
  2 环境缺失
  3 运行失败
"""

from __future__ import annotations

import json
import os
import re
import asyncio
import sys
import time
import uuid
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# 确保可导入 scripts/*（避免以文件路径执行时 sys.path 仅包含 scripts/monitoring）
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.monitoring.e2e_trace import TraceLogger, TraceReport, _safe_sse_event


def _load_dotenv(repo_root: Path) -> tuple[dict[str, str], list[str]]:
    """最小 dotenv 读取器（仅供 E2E 脚本使用，避免依赖额外包）。"""

    candidates = [".env", ".env.local", ".env.docker.local"]
    merged: dict[str, str] = {}
    loaded: list[str] = []
    for filename in candidates:
        path = repo_root / filename
        if not path.exists():
            continue
        loaded.append(filename)
        env: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and value:
                env[key] = value
        merged.update(env)
    return merged, loaded


def _get_env_value(name: str, *fallback_names: str, default: str = "", dotenv: dict[str, str] | None = None) -> str:
    for key in (name, *fallback_names):
        v = (os.getenv(key) or "").strip()
        if v:
            return v
        if dotenv:
            dv = str(dotenv.get(key) or "").strip()
            if dv:
                return dv
        # WSL 兼容：若变量只在 Windows 环境中设置，尝试从 cmd.exe 读取
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", f"echo %{key}%"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            win_value = (result.stdout or "").strip()
            if win_value and win_value != f"%{key}%":
                return win_value
        except Exception:
            pass
    return default


def _require_env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise KeyError(name)
    return v


def _as_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_asset_prompts(repo_root: Path) -> tuple[str, list[dict[str, Any]]]:
    """
    返回：
    - system_prompt_text：standard_prompt.txt + serp_prompt.md（合并）
    - openai_tools_schema：由 assets/prompts/standard_serp_v2.json 的 tools 清单生成
    """
    prompts_dir = repo_root / "assets" / "prompts"
    system_text = _read_text(prompts_dir / "standard_prompt.txt").strip()
    serp_text = _read_text(prompts_dir / "serp_prompt.md").strip()

    header = (
        "你必须严格按 docs/ai预期响应结构.md 输出（ThinkingML v4.5 XML）。"
        "若校验失败，整段输出必须为 <<ParsingError>>。"
    )
    system_prompt = "\n\n".join([part for part in (header, system_text, serp_text) if part])

    raw = json.loads(_read_text(prompts_dir / "standard_serp_v2.json"))
    tool_specs = raw.get("tools") if isinstance(raw, dict) else None
    if not isinstance(tool_specs, list):
        tool_specs = []

    tools: list[dict[str, Any]] = []
    for item in tool_specs:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        params = item.get("params")
        param_names = [str(v).strip() for v in (params or []) if isinstance(v, str) and str(v).strip()]
        properties = {p: {"type": "string", "description": p} for p in param_names}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"GymBro tool: {name}",
                    "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
                },
            }
        )

    return system_prompt, tools


def _build_tools_prompt_text(tools: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict):
            name = fn.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    names = list(dict.fromkeys(names))
    lines = [
        "可用工具（如需调用）：",
        *[f"- {name}" for name in names[:50]],
        "",
        "规则：仅在确有必要时调用；不要编造工具输出；输出结构仍必须满足 docs/ai预期响应结构.md。",
    ]
    return "\n".join(lines).strip()


ALLOWED_TAGS = {"think", "serp", "thinking", "phase", "title", "final"}
TAG_RE = re.compile(r"<\s*/?\s*([a-zA-Z]+)(?:\s+[^>]*)?>")


def _validate_expected_structure(reply: str) -> tuple[bool, str]:
    text = (reply or "").strip()
    if not text:
        return False, "empty_reply"
    if text == "<<ParsingError>>":
        return False, "parsing_error_marker"
    if "<thinking>" not in text or "</thinking>" not in text or "<final>" not in text or "</final>" not in text:
        return False, "missing_required_blocks"
    if text.find("</thinking>") > text.find("<final>"):
        return False, "invalid_sequence_thinking_final"
    if "<phase" not in text or "<title>" not in text:
        return False, "missing_phase_or_title"

    for match in TAG_RE.finditer(text):
        tag = (match.group(1) or "").strip()
        if tag and tag.lower() not in ALLOWED_TAGS:
            return False, f"unexpected_tag:{tag}"

    if "<!-- <serp_queries>" not in text:
        return False, "missing_serp_queries_block"
    return True, "ok"


def _find_routed(frames: list[dict[str, Any]]) -> dict[str, Any] | None:
    for evt in frames:
        if not isinstance(evt, dict):
            continue
        if evt.get("event") != "status":
            continue
        data = evt.get("data")
        if isinstance(data, dict) and data.get("state") == "routed":
            return data
    return None


def _build_message_payload(
    *,
    text: str,
    conversation_id: Optional[str],
    prompt_mode: str,
    openai: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """对齐 Web `web/src/api/aiModelSuite.js::createMessage` 的最小构建逻辑。"""
    has_text = isinstance(text, str) and bool(text.strip())
    messages = openai.get("messages")
    has_messages = isinstance(messages, list) and len(messages) > 0
    if not has_text and not has_messages:
        raise RuntimeError("text 或 openai.messages 至少提供一个")

    resolved_prompt_mode = "passthrough" if prompt_mode == "passthrough" else "server"
    payload: dict[str, Any] = {
        "conversation_id": conversation_id or None,
        "metadata": {"source": "e2e_script", "timestamp": _iso_now(), **(metadata or {})},
        "skip_prompt": resolved_prompt_mode == "passthrough",
    }
    if has_text:
        payload["text"] = text.strip()

    model = openai.get("model")
    if isinstance(model, str) and model.strip():
        payload["model"] = model.strip()

    if has_messages:
        if resolved_prompt_mode == "server":
            payload["messages"] = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
        else:
            payload["messages"] = [m for m in messages if isinstance(m, dict)]

    for key in ("system_prompt", "tools", "tool_choice", "temperature", "top_p", "max_tokens"):
        if key in openai and openai[key] is not None:
            payload[key] = openai[key]

    return payload


async def _post_json(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float = 30.0,
) -> httpx.Response:
    return await client.post(url, headers=headers, json=payload, timeout=timeout)


async def _login_admin(*, api_base: str, username: str, password: str, request_id: str, log: TraceLogger) -> str:
    url = api_base.rstrip("/") + "/base/access_token"
    started = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await _post_json(
            client,
            url=url,
            headers={"Content-Type": "application/json", "X-Request-Id": request_id},
            payload={"username": username, "password": password},
        )
    finished = time.time()
    ok = resp.status_code == 200 and isinstance(resp.json(), dict) and resp.json().get("code") == 200
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    token = ((data.get("data") or {}) if isinstance(data, dict) else {}).get("access_token")
    log.step(
        "login_admin",
        ok=bool(ok and token),
        started_at=started,
        finished_at=finished,
        request={"url": url, "headers": {"X-Request-Id": request_id}, "body": {"username": username, "password": "<redacted>"}},
        response={"status_code": resp.status_code, "body": data},
    )
    if not token:
        raise RuntimeError("admin_login_failed")
    return str(token)


async def _ensure_xai_endpoint(
    *,
    api_base: str,
    token: str,
    request_id: str,
    base_url: str,
    api_key: str,
    provider_model: str,
    log: TraceLogger,
) -> int:
    url_list = api_base.rstrip("/") + "/llm/models"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Request-Id": request_id}
    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        resp = await client.get(url_list, headers=headers, params={"view": "endpoints", "page": 1, "page_size": 200})
        finished = time.time()
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    endpoints = data.get("data") if isinstance(data, dict) else None
    endpoint_id: int | None = None
    if isinstance(endpoints, list):
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            name = str(ep.get("name") or "").strip().lower()
            ep_base = str(ep.get("base_url") or "").strip().lower()
            if name == "xai" or "x.ai" in ep_base:
                try:
                    endpoint_id = int(ep.get("id"))
                except Exception:
                    endpoint_id = None
                break
    log.step(
        "list_endpoints",
        ok=resp.status_code == 200,
        started_at=started,
        finished_at=finished,
        request={"url": url_list, "headers": {"X-Request-Id": request_id}, "query": {"view": "endpoints"}},
        response={"status_code": resp.status_code, "body": data},
        notes={"found_endpoint_id": endpoint_id},
    )

    payload = {
        "name": "xai",
        "base_url": base_url,
        "model": provider_model,
        "api_key": api_key,
        "timeout": 60,
        "is_active": True,
        "is_default": True,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        if endpoint_id is None:
            resp2 = await client.post(url_list, headers=headers, json=payload)
        else:
            resp2 = await client.put(url_list, headers=headers, json={"id": endpoint_id, **payload})
        finished = time.time()
    body2 = resp2.json() if resp2.headers.get("content-type", "").startswith("application/json") else {}
    ok = resp2.status_code == 200 and isinstance(body2, dict) and body2.get("code") == 200
    saved = body2.get("data") if isinstance(body2, dict) else None
    if isinstance(saved, dict):
        try:
            endpoint_id = int(saved.get("id"))
        except Exception:
            pass
    log.step(
        "upsert_xai_endpoint",
        ok=bool(ok and endpoint_id),
        started_at=started,
        finished_at=finished,
        request={"url": url_list, "headers": {"X-Request-Id": request_id}, "body": {"name": "xai", "base_url": base_url, "model": provider_model}},
        response={"status_code": resp2.status_code, "body": body2},
        notes={"endpoint_id": endpoint_id},
    )
    if not endpoint_id:
        raise RuntimeError("upsert_xai_endpoint_failed")
    return int(endpoint_id)


async def _upsert_mapping(
    *,
    api_base: str,
    token: str,
    request_id: str,
    scope_key: str,
    provider_model: str,
    log: TraceLogger,
) -> None:
    url = api_base.rstrip("/") + "/llm/model-groups"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Request-Id": request_id}
    payload = {
        "scope_type": "global",
        "scope_key": scope_key,
        "name": "xAI",
        "default_model": provider_model,
        "candidates": [provider_model],
        "is_active": True,
        "metadata": {"source": "e2e_script"},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        resp = await client.post(url, headers=headers, json=payload)
        finished = time.time()
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    ok = resp.status_code == 200 and isinstance(body, dict) and body.get("code") == 200
    log.step(
        "upsert_model_mapping",
        ok=ok,
        started_at=started,
        finished_at=finished,
        request={"url": url, "headers": {"X-Request-Id": request_id}, "body": {"scope_type": "global", "scope_key": scope_key, "default_model": provider_model}},
        response={"status_code": resp.status_code, "body": body},
    )
    if not ok:
        raise RuntimeError("upsert_model_mapping_failed")


async def _upsert_and_activate_prompt(
    *,
    api_base: str,
    token: str,
    request_id: str,
    name: str,
    prompt_type: str,
    content: str,
    tools_json: Any,
    log: TraceLogger,
) -> int:
    url_list = api_base.rstrip("/") + "/llm/prompts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Request-Id": request_id}

    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        resp = await client.get(url_list, headers=headers, params={"keyword": name, "prompt_type": prompt_type, "page": 1, "page_size": 20})
        finished = time.time()
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    items = data.get("data") if isinstance(data, dict) else None
    prompt_id: int | None = None
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("name") or "") == name:
                try:
                    prompt_id = int(item.get("id"))
                except Exception:
                    prompt_id = None
                break
    log.step(
        f"find_prompt_{prompt_type}",
        ok=resp.status_code == 200,
        started_at=started,
        finished_at=finished,
        request={"url": url_list, "headers": {"X-Request-Id": request_id}, "query": {"keyword": name, "prompt_type": prompt_type}},
        response={"status_code": resp.status_code, "body": data},
        notes={"prompt_id": prompt_id},
    )

    payload = {
        "name": name,
        "content": content,
        "prompt_type": prompt_type,
        "is_active": True,
    }
    if tools_json is not None:
        payload["tools_json"] = tools_json

    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        if prompt_id is None:
            resp2 = await client.post(url_list, headers=headers, json=payload)
        else:
            resp2 = await client.put(f"{url_list}/{prompt_id}", headers=headers, json=payload)
        finished = time.time()
    body2 = resp2.json() if resp2.headers.get("content-type", "").startswith("application/json") else {}
    ok = resp2.status_code == 200 and isinstance(body2, dict) and body2.get("code") == 200
    saved = body2.get("data") if isinstance(body2, dict) else None
    if isinstance(saved, dict):
        try:
            prompt_id = int(saved.get("id"))
        except Exception:
            pass
    log.step(
        f"upsert_prompt_{prompt_type}",
        ok=bool(ok and prompt_id),
        started_at=started,
        finished_at=finished,
        request={"url": url_list, "headers": {"X-Request-Id": request_id}, "body": {"name": name, "prompt_type": prompt_type}},
        response={"status_code": resp2.status_code, "body": body2},
        notes={"prompt_id": prompt_id},
    )
    if not prompt_id:
        raise RuntimeError(f"upsert_prompt_failed:{prompt_type}")

    url_activate = f"{url_list}/{prompt_id}/activate"
    async with httpx.AsyncClient(timeout=30.0) as client:
        started = time.time()
        resp3 = await client.post(url_activate, headers=headers, json={})
        finished = time.time()
    body3 = resp3.json() if resp3.headers.get("content-type", "").startswith("application/json") else {}
    ok3 = resp3.status_code == 200 and isinstance(body3, dict) and body3.get("code") == 200
    log.step(
        f"activate_prompt_{prompt_type}",
        ok=ok3,
        started_at=started,
        finished_at=finished,
        request={"url": url_activate, "headers": {"X-Request-Id": request_id}},
        response={"status_code": resp3.status_code, "body": body3},
        notes={"prompt_id": prompt_id},
    )
    if not ok3:
        raise RuntimeError(f"activate_prompt_failed:{prompt_type}")
    return int(prompt_id)


async def _create_message(*, api_base: str, token: str, request_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    url = api_base.rstrip("/") + "/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Request-Id": request_id}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 202:
            raise RuntimeError(f"/messages 创建失败：HTTP {resp.status_code}")
        data = resp.json()
        mid = data.get("message_id")
        cid = data.get("conversation_id")
        if not mid or not cid:
            raise RuntimeError("/messages 响应缺少 message_id/conversation_id")
        return str(mid), str(cid)


async def _consume_sse(
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

    def flush() -> dict[str, Any] | None:
        nonlocal data_lines
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
                    evt = flush()
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


@dataclass(frozen=True)
class RunResult:
    ok: bool
    message_id: str
    conversation_id: str
    provider: str | None
    resolved_model: str | None
    reply: str | None
    reason: str | None = None


async def _run_one(
    *,
    api_base: str,
    token: str,
    request_id: str,
    text: str,
    prompt_mode: str,
    openai: dict[str, Any],
    expected_provider: str,
    expected_resolved_model: str,
    log: TraceLogger,
    step_prefix: str,
) -> RunResult:
    payload = _build_message_payload(text=text, conversation_id=None, prompt_mode=prompt_mode, openai=openai, metadata={})

    started = time.time()
    mid, cid = await _create_message(api_base=api_base, token=token, request_id=request_id, payload=payload)
    finished = time.time()
    log.step(
        f"{step_prefix}_create_message",
        ok=True,
        started_at=started,
        finished_at=finished,
        request={"url": f"{api_base.rstrip('/')}/messages", "headers": {"X-Request-Id": request_id}, "body": payload},
        response={"message_id": mid, "conversation_id": cid},
    )

    started = time.time()
    sse = await _consume_sse(api_base=api_base, token=token, request_id=request_id, message_id=mid, conversation_id=cid)
    finished = time.time()
    final = sse.get("final") or {}
    frames = sse.get("frames") or []
    log.step(
        f"{step_prefix}_consume_sse",
        ok=True,
        started_at=started,
        finished_at=finished,
        request={"url": f"{api_base.rstrip('/')}/messages/{mid}/events", "headers": {"X-Request-Id": request_id}},
        response={"final": final, "frames_count": len(frames)},
    )

    routed = _find_routed(frames if isinstance(frames, list) else [])
    provider = routed.get("provider") if isinstance(routed, dict) else None
    resolved_model = routed.get("resolved_model") if isinstance(routed, dict) else None

    reply = None
    if isinstance(final, dict) and final.get("event") == "completed":
        data = final.get("data")
        if isinstance(data, dict):
            reply = str(data.get("reply") or "")

    if provider != expected_provider or resolved_model != expected_resolved_model:
        return RunResult(
            ok=False,
            message_id=mid,
            conversation_id=cid,
            provider=str(provider) if provider is not None else None,
            resolved_model=str(resolved_model) if resolved_model is not None else None,
            reply=reply,
            reason="routed_mismatch",
        )

    ok, reason = _validate_expected_structure(reply or "")
    return RunResult(
        ok=ok,
        message_id=mid,
        conversation_id=cid,
        provider=str(provider) if provider is not None else None,
        resolved_model=str(resolved_model) if resolved_model is not None else None,
        reply=reply,
        reason=reason if not ok else None,
    )


async def main() -> int:
    request_id = uuid.uuid4().hex
    repo_root = Path(__file__).resolve().parents[2]
    dotenv, dotenv_files = _load_dotenv(repo_root)
    report = TraceReport(
        request_id=request_id,
        context={
            "api_base": os.getenv("E2E_API_BASE") or "http://127.0.0.1:9999/api/v1",
            "mapped_model_key": os.getenv("E2E_MAPPED_MODEL_KEY") or "global:xai",
            "xai_base_url": _get_env_value("XAI_API_BASE_URL", "XAI_BASEURL", default="https://api.x.ai", dotenv=dotenv),
            "xai_provider_model": os.getenv("XAI_PROVIDER_MODEL") or "grok-4.1-思考",
            "dotenv_files": dotenv_files,
        },
    )
    log = TraceLogger(report, verbose=_as_bool(os.getenv("E2E_VERBOSE") or "true", default=True))

    xai_api_key = _get_env_value("XAI_API_KEY", default="", dotenv=dotenv)
    if not xai_api_key:
        hint = {
            "dotenv_files": dotenv_files,
            "has_XAI_API_KEY_in_dotenv": "XAI_API_KEY" in dotenv,
            "has_XAI_BASEURL_in_dotenv": "XAI_BASEURL" in dotenv or "XAI_API_BASE_URL" in dotenv,
            "note": "请确认把 XAI_API_KEY 写入仓库根目录 .env.local（或 .env/.env.docker.local），或在当前 WSL shell export 后再运行脚本。",
        }
        log.step("missing_env", ok=False, started_at=time.time(), finished_at=time.time(), notes=hint)
        return 2

    api_base = (os.getenv("E2E_API_BASE") or "http://127.0.0.1:9999/api/v1").strip()
    username = (os.getenv("E2E_ADMIN_USERNAME") or "admin").strip()
    password = (os.getenv("E2E_ADMIN_PASSWORD") or "123456").strip()
    xai_base_url = _get_env_value("XAI_API_BASE_URL", "XAI_BASEURL", default="https://api.x.ai", dotenv=dotenv).strip()
    provider_model = (os.getenv("XAI_PROVIDER_MODEL") or "grok-4.1-思考").strip()

    mapped_key = (os.getenv("E2E_MAPPED_MODEL_KEY") or "global:xai").strip()
    scope_key = mapped_key.split(":", 1)[1] if ":" in mapped_key else mapped_key
    text = (os.getenv("E2E_MESSAGE_TEXT") or "给我一份三分化训练方案").strip()

    system_prompt_text, openai_tools = _load_asset_prompts(repo_root)
    tools_prompt_text = _build_tools_prompt_text(openai_tools)

    output_path = os.getenv("E2E_OUTPUT_PATH") or str(
        repo_root / "e2e" / "real_user_sse" / "artifacts" / f"xai_mapped_model_trace_{request_id}.json"
    )

    try:
        token = await _login_admin(api_base=api_base, username=username, password=password, request_id=request_id, log=log)

        await _ensure_xai_endpoint(
            api_base=api_base,
            token=token,
            request_id=request_id,
            base_url=xai_base_url,
            api_key=xai_api_key,
            provider_model=provider_model,
            log=log,
        )
        await _upsert_mapping(
            api_base=api_base,
            token=token,
            request_id=request_id,
            scope_key=scope_key,
            provider_model=provider_model,
            log=log,
        )
        await _upsert_and_activate_prompt(
            api_base=api_base,
            token=token,
            request_id=request_id,
            name="GymBro Strict XML (Assets)",
            prompt_type="system",
            content=system_prompt_text,
            tools_json=None,
            log=log,
        )
        await _upsert_and_activate_prompt(
            api_base=api_base,
            token=token,
            request_id=request_id,
            name="GymBro Tools (Assets)",
            prompt_type="tools",
            content=tools_prompt_text,
            tools_json=openai_tools,
            log=log,
        )

        # 1) server 模式：不透传（后端注入 prompt/tools）
        r1 = await _run_one(
            api_base=api_base,
            token=token,
            request_id=request_id,
            text=text,
            prompt_mode="server",
            openai={"model": mapped_key},
            expected_provider="xai",
            expected_resolved_model=provider_model,
            log=log,
            step_prefix="server",
        )
        log.step(
            "server_verify",
            ok=r1.ok,
            started_at=time.time(),
            finished_at=time.time(),
            notes={"reason": r1.reason, "provider": r1.provider, "resolved_model": r1.resolved_model},
        )
        if not r1.ok:
            raise RuntimeError(f"server_mode_failed:{r1.reason}")

        # 2) passthrough 模式：全量透传 system/messages/tools
        passthrough_openai = {
            "model": mapped_key,
            "messages": [{"role": "system", "content": system_prompt_text}, {"role": "user", "content": text}],
            "tools": openai_tools,
            "tool_choice": "auto",
        }
        r2 = await _run_one(
            api_base=api_base,
            token=token,
            request_id=request_id,
            text="",
            prompt_mode="passthrough",
            openai=passthrough_openai,
            expected_provider="xai",
            expected_resolved_model=provider_model,
            log=log,
            step_prefix="passthrough",
        )
        log.step(
            "passthrough_verify",
            ok=r2.ok,
            started_at=time.time(),
            finished_at=time.time(),
            notes={"reason": r2.reason, "provider": r2.provider, "resolved_model": r2.resolved_model},
        )
        if not r2.ok:
            raise RuntimeError(f"passthrough_mode_failed:{r2.reason}")

        report.finished_at = time.time()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        report.write_json(Path(output_path))
        log.log(f"done trace={output_path}")
        return 0
    except Exception as exc:
        report.finished_at = time.time()
        try:
            report.write_json(Path(output_path))
        except Exception:
            pass
        log.log(f"failed error={type(exc).__name__}")
        return 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
