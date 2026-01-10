#!/usr/bin/env python3
"""
Prompt / Protocol 调试器（E2E，目标：稳定产出符合 docs/ai预期响应结构.md 的 ThinkingML v4.5 XML）。

用途：
- 在不改业务代码的前提下，持续迭代 system prompt / tool prompt / 调用协议组合，
  用真实 /messages + SSE /events 链路验证拼接后的 XML 是否满足契约（SSOT：_validate_thinkingml）。

支持维度（最小集合）：
- prompt_mode: server | passthrough
- result_mode: xml_plaintext | auto（默认 xml_plaintext）
- tool_choice: none/auto/required（passthrough 下生效）

注意：
- 该脚本默认会将 assets/prompts/* 写入并 activate 到后端 prompt SSOT（需 admin token）。
- 若你正在“手动调试 prompt 文件内容”，改完文件后再次运行即可得到最新结果。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.monitoring.local_mock_ai_conversation_e2e import (  # noqa: E402
    _load_prompt_assets,
    _parse_tools_from_tool_md,
    _validate_thinkingml,
)

REQUEST_ID_HEADER = "X-Request-Id"


def _normalize_api_base(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:9999/api/v1"
    text = text.rstrip("/")
    if text.endswith("/api/v1"):
        return text
    return text + "/api/v1"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _sha256(text: str) -> str:
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


@dataclass(frozen=True)
class ProtocolCase:
    prompt_mode: str
    result_mode: str
    tool_choice: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prompt/Protocol tuner E2E (ThinkingML v4.5 contract)")
    parser.add_argument("--api-base", default=os.getenv("E2E_API_BASE", "http://127.0.0.1:9999/api/v1"))
    parser.add_argument("--username", default=os.getenv("E2E_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("E2E_ADMIN_PASSWORD", "123456"))
    parser.add_argument("--models", nargs="*", default=None, help="映射名列表（如 xai deepseek）；不传则取全部 mapped models")

    parser.add_argument(
        "--prompt-mode",
        nargs="*",
        default=["server"],
        help="server|passthrough，可多值（做协议矩阵）。默认 server。",
    )
    parser.add_argument(
        "--result-mode",
        nargs="*",
        default=["xml_plaintext"],
        help="xml_plaintext|auto，可多值。默认 xml_plaintext（用于 XML 契约回归）。",
    )
    parser.add_argument(
        "--tool-choice",
        nargs="*",
        default=["none"],
        help="none|auto|required，可多值（仅 passthrough 下生效）。默认 none。",
    )
    parser.add_argument("--turns", type=int, default=_as_int(os.getenv("E2E_TURNS"), 1))
    parser.add_argument("--runs", type=int, default=_as_int(os.getenv("E2E_RUNS"), 1))
    parser.add_argument("--throttle-seconds", type=float, default=_as_float(os.getenv("E2E_THROTTLE_SECONDS", 0.35), 0.35))
    parser.add_argument("--stream-timeout", type=float, default=_as_float(os.getenv("E2E_STREAM_TIMEOUT", 180), 180))
    parser.add_argument("--max-events", type=int, default=_as_int(os.getenv("E2E_MAX_EVENTS", 4000), 4000))

    parser.add_argument(
        "--activate-prompts",
        action="store_true",
        default=True,
        help="写入并 activate prompts（SSOT：assets/prompts/*）。默认开启。",
    )
    parser.add_argument(
        "--no-activate-prompts",
        dest="activate_prompts",
        action="store_false",
        help="跳过 prompt 写入/激活（使用当前 DB 里已激活的 prompt）。",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=os.getenv("E2E_ARTIFACTS_DIR", "e2e/prompt_protocol_tuner/artifacts"),
        help="脱敏产物输出目录（默认已 gitignore）。",
    )
    parser.add_argument("--verbose", action="store_true", default=str(os.getenv("E2E_VERBOSE", "1")).strip().lower() in ("1", "true", "yes"))
    return parser.parse_args()


def _print(msg: str, *, verbose: bool) -> None:
    if verbose:
        print(msg)


async def _dashboard_login(client: httpx.AsyncClient, *, username: str, password: str) -> str:
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
    return token


async def _ensure_prompts_activated(
    client: httpx.AsyncClient,
    *,
    auth_headers: dict[str, str],
    verbose: bool,
) -> dict[str, Any]:
    """
    将 assets/prompts/* 写入并激活到后端（SSOT）。

    返回：记录本次写入的 prompt 摘要（不包含原文）。
    """

    profile, serp_prompt, tool_prompt = _load_prompt_assets()
    tools_schema = _parse_tools_from_tool_md(tool_prompt)

    # prompt SSOT：沿用现有 E2E 脚本的命名约定（避免影子 prompt）。
    # 说明：若后端接口策略变更，这里会尽早 fail，避免“以为激活了但实际没生效”。
    payload = {
        "name": "standard_serp_v2",
        "profile": profile,
        "system_prompt": serp_prompt,
        "tools_prompt": tool_prompt,
        "tools_json": json.dumps(tools_schema, ensure_ascii=False),
        "is_active": True,
    }
    request_id = uuid.uuid4().hex
    resp = await client.post(
        "/llm/prompts/upsert-and-activate",
        json=payload,
        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    _print(f"[prompts] activated name=standard_serp_v2 request_id={request_id}", verbose=verbose)

    return {
        "name": "standard_serp_v2",
        "profile_sha256": _sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True)),
        "system_prompt_sha256": _sha256(serp_prompt),
        "tools_prompt_sha256": _sha256(tool_prompt),
        "tools_count": len(tools_schema),
    }


async def _list_mapped_models(client: httpx.AsyncClient, *, auth_headers: dict[str, str]) -> list[str]:
    request_id = uuid.uuid4().hex
    resp = await client.get(
        "/llm/models",
        params={"view": "mapped"},
        headers={**auth_headers, REQUEST_ID_HEADER: request_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = _unwrap_data(resp.json()) or []
    names: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
                names.append(item["name"].strip())
    return names


async def _collect_sse_reply(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    stream_timeout: float,
    max_events: int,
) -> tuple[list[dict[str, Any]], str, Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    reply_accum = ""
    completed: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None

    async with client.stream("GET", url, headers=headers, timeout=stream_timeout) as response:
        response.raise_for_status()

        current_event = "message"
        data_lines: list[str] = []

        def flush() -> Optional[dict[str, Any]]:
            nonlocal current_event, data_lines
            if not data_lines:
                current_event = "message"
                return None
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed: Any = json.loads(raw)
            except Exception:
                parsed = raw
            ev = {"event": current_event, "data": parsed}
            current_event = "message"
            return ev

        lines = response.aiter_lines()
        for _ in range(max_events * 8):
            try:
                line = await asyncio.wait_for(lines.__anext__(), timeout=8.0)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                break

            if line is None:
                break
            line = line.rstrip("\r")

            if not line:
                ev = flush()
                if ev:
                    events.append(ev)
                    if ev["event"] == "content_delta" and isinstance(ev.get("data"), dict):
                        delta = ev["data"].get("delta")
                        if isinstance(delta, str) and delta:
                            reply_accum += delta
                    if ev["event"] == "completed":
                        completed = ev.get("data") if isinstance(ev.get("data"), dict) else None
                        break
                    if ev["event"] == "error":
                        error = ev.get("data") if isinstance(ev.get("data"), dict) else None
                        break
                continue

            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
                continue

        tail = flush()
        if tail:
            events.append(tail)

    return events, reply_accum, completed, error


def _sanitize_artifact_event(ev: dict[str, Any]) -> dict[str, Any]:
    event = str(ev.get("event") or "")
    data = ev.get("data")
    if not isinstance(data, dict):
        return {"event": event, "data": data}
    safe = dict(data)
    if event == "content_delta":
        delta = safe.get("delta")
        safe["delta_len"] = len(delta) if isinstance(delta, str) else 0
        safe.pop("delta", None)
    if event == "upstream_raw":
        raw = safe.get("raw")
        safe["raw_len"] = len(raw) if isinstance(raw, str) else 0
        safe.pop("raw", None)
    if event in {"completed", "error"}:
        reply = safe.get("reply")
        if isinstance(reply, str):
            safe["reply_len"] = len(reply)
            safe.pop("reply", None)
    return {"event": event, "data": safe}


async def _run_case(
    client: httpx.AsyncClient,
    *,
    model: str,
    case: ProtocolCase,
    token: str,
    user_text: str,
    tools_schema: list[dict[str, Any]],
    system_prompt: str,
    stream_timeout: float,
    max_events: int,
    artifacts_dir: Path,
    verbose: bool,
) -> tuple[bool, str]:
    create_request_id = uuid.uuid4().hex
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 构建 /messages 请求体
    payload: dict[str, Any] = {
        "model": model,
        "conversation_id": None,
        "metadata": {
            "scenario": "prompt_protocol_tuner",
            "prompt_mode": case.prompt_mode,
            "result_mode": case.result_mode,
            "tool_choice": case.tool_choice,
        },
        "result_mode": case.result_mode,
    }

    if case.prompt_mode == "passthrough":
        payload["skip_prompt"] = True
        payload["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        payload["tools"] = tools_schema
        payload["tool_choice"] = case.tool_choice
    else:
        payload["skip_prompt"] = False
        payload["text"] = user_text

    created = await client.post(
        "/messages",
        json=payload,
        headers={**auth_headers, REQUEST_ID_HEADER: create_request_id},
        timeout=60.0,
    )
    created.raise_for_status()
    obj = created.json() or {}
    message_id = str(obj.get("message_id") or "")
    conversation_id = str(obj.get("conversation_id") or "")
    if not message_id:
        raise RuntimeError("missing_message_id")

    stream_request_id = uuid.uuid4().hex
    events_url = f"/messages/{message_id}/events"
    if conversation_id:
        events_url += f"?conversation_id={conversation_id}"

    events, reply_accum, completed, error = await _collect_sse_reply(
        client,
        url=events_url,
        headers={**auth_headers, "Accept": "text/event-stream", REQUEST_ID_HEADER: stream_request_id},
        stream_timeout=stream_timeout,
        max_events=max_events,
    )

    ok = False
    reason = "unknown"
    if error is not None:
        ok = False
        reason = str(error.get("code") or "sse_error")
    else:
        # 仅 xml_plaintext 需要验证 ThinkingML v4.5；raw_passthrough 的 XML 结构不作为回归目标。
        if case.result_mode in {"xml_plaintext", "auto"}:
            ok, reason = _validate_thinkingml(reply_accum)
        else:
            ok = True
            reason = "ok"

    # artifacts（脱敏）
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = artifacts_dir / f"tuner_{ts}_{model}_{case.prompt_mode}_{case.result_mode}_{case.tool_choice}_{message_id}.json"
    safe_events = [_sanitize_artifact_event(e) for e in events]
    out_obj = {
        "ok": ok,
        "reason": reason,
        "model": model,
        "prompt_mode": case.prompt_mode,
        "result_mode": case.result_mode,
        "tool_choice": case.tool_choice,
        "create_request_id": create_request_id,
        "sse_request_id": stream_request_id,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "reply_len": len(reply_accum),
        "completed": completed,
        "error": error,
        "events": safe_events,
    }
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    flag = "PASS" if ok else "FAIL"
    _print(
        f"{flag} model={model} prompt_mode={case.prompt_mode} result_mode={case.result_mode} tool_choice={case.tool_choice} reason={reason} artifact={out_path}",
        verbose=verbose,
    )
    return ok, reason


async def main() -> int:
    args = _parse_args()
    api_base = _normalize_api_base(args.api_base)
    verbose = bool(args.verbose)

    prompts_summary: dict[str, Any] = {}
    profile, serp_prompt, tool_prompt = _load_prompt_assets()
    tools_schema = _parse_tools_from_tool_md(tool_prompt)
    system_prompt = serp_prompt
    system_prompt_sha = _sha256(system_prompt)

    async with httpx.AsyncClient(base_url=api_base, timeout=60.0) as client:
        # 需要 admin token 才能写入/激活 prompts；若只想跑现有已激活 prompt，可关闭 activate。
        token = await _dashboard_login(client, username=args.username, password=args.password)
        auth_headers = {"Authorization": f"Bearer {token}"}

        if args.activate_prompts:
            prompts_summary = await _ensure_prompts_activated(client, auth_headers=auth_headers, verbose=verbose)

        models = args.models
        if not models:
            models = await _list_mapped_models(client, auth_headers=auth_headers)
        models = [str(m or "").strip() for m in (models or []) if str(m or "").strip()]
        if not models:
            _print("[WARN] no mapped models found", verbose=True)
            return 2

        # 构建协议矩阵（KISS：只做必要笛卡尔积）
        prompt_modes = [str(x or "").strip() for x in (args.prompt_mode or []) if str(x or "").strip()]
        result_modes = [str(x or "").strip() for x in (args.result_mode or []) if str(x or "").strip()]
        tool_choices = [str(x or "").strip() for x in (args.tool_choice or []) if str(x or "").strip()]

        def norm_prompt_mode(v: str) -> str:
            return "passthrough" if v == "passthrough" else "server"

        def norm_result_mode(v: str) -> str:
            return v if v in {"xml_plaintext", "raw_passthrough", "auto"} else "xml_plaintext"

        def norm_tool_choice(v: str) -> str:
            return v if v in {"none", "auto", "required"} else "none"

        cases: list[ProtocolCase] = []
        for pm in prompt_modes:
            for rm in result_modes:
                for tc in tool_choices:
                    cases.append(
                        ProtocolCase(
                            prompt_mode=norm_prompt_mode(pm),
                            result_mode=norm_result_mode(rm),
                            tool_choice=norm_tool_choice(tc),
                        )
                    )

        artifacts_dir = Path(args.artifacts_dir)
        summary_path = artifacts_dir / "SUMMARY.json"
        failures: list[dict[str, Any]] = []

        user_text = "给我一份三分化训练方案（要求严格输出 ThinkingML v4.5 XML）。"

        total = 0
        passed = 0
        for run_idx in range(int(args.runs)):
            for model in models:
                for case in cases:
                    for turn_idx in range(int(args.turns)):
                        total += 1
                        ok, reason = await _run_case(
                            client,
                            model=model,
                            case=case,
                            token=token,
                            user_text=user_text,
                            tools_schema=tools_schema,
                            system_prompt=system_prompt,
                            stream_timeout=float(args.stream_timeout),
                            max_events=int(args.max_events),
                            artifacts_dir=artifacts_dir,
                            verbose=verbose,
                        )
                        if ok:
                            passed += 1
                        else:
                            failures.append(
                                {
                                    "model": model,
                                    "prompt_mode": case.prompt_mode,
                                    "result_mode": case.result_mode,
                                    "tool_choice": case.tool_choice,
                                    "reason": reason,
                                    "run": run_idx + 1,
                                    "turn": turn_idx + 1,
                                }
                            )
                        await asyncio.sleep(float(args.throttle_seconds))

        out_summary = {
            "api_base": api_base,
            "models": models,
            "cases": [case.__dict__ for case in cases],
            "runs": int(args.runs),
            "turns": int(args.turns),
            "system_prompt_sha256": system_prompt_sha,
            "profile_sha256": _sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True)),
            "tools_prompt_sha256": _sha256(tool_prompt),
            "tools_count": len(tools_schema),
            "prompts": prompts_summary or None,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "failures": failures[:200],
        }
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(out_summary, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"SUMMARY total={total} passed={passed} failed={total - passed} summary={summary_path}")
        return 0 if total == passed else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

