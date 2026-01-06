#!/usr/bin/env python3
"""
Cliproxy（本地 OpenAI-compat 代理）模型 E2E（不做 mock）：
1) Dashboard 本地 admin 登录（/api/v1/base/access_token）获取 JWT
2) 定位并刷新本地端点（base_url=CLIPROXY_BASE_URL）
3) 基于端点 /v1/models 返回的 model_list，为每个模型创建临时 mapping（tenant scope）
4) 逐个发起 messages → SSE，校验 routed/completed
5) 清理临时 mapping，输出脱敏 trace

必需环境变量：
  - 无（默认使用本地 admin/123456；端点需已在后台配置好 api_key）

可选环境变量：
  - E2E_API_BASE                默认 http://127.0.0.1:9999/api/v1
  - E2E_ADMIN_USERNAME          默认 admin
  - E2E_ADMIN_PASSWORD          默认 123456
  - CLIPROXY_BASE_URL           默认 http://172.19.32.1:8317
  - E2E_MAX_MODELS              默认 0（表示不限制）
  - E2E_MODEL_FILTER            逗号分隔：仅测试指定 model id（如 gpt-5.2,claude-opus-4-5-20251101）
  - E2E_FAIL_FAST               1/true 遇到失败立即退出（默认 false）
  - E2E_OUTPUT_PATH             默认 e2e/real_user_sse/artifacts/cliproxy_models_trace_<request_id>.json
  - E2E_VERBOSE                 1/true 打印步骤日志（默认 true）

退出码：
  0 全部通过
  2 环境缺失/前置不满足
  3 运行失败（含部分模型失败）
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
import time
import uuid
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.monitoring.e2e_trace import TraceLogger, TraceReport, _safe_sse_event


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name) or default).strip()


def _slugify(value: str, *, max_len: int = 64) -> str:
    text = str(value or "").strip()
    if not text:
        return "model"
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "model"
    return text[:max_len]


async def _login(api_base: str, *, username: str, password: str, request_id: str, client: httpx.AsyncClient, log: TraceLogger) -> str:
    started = time.time()
    resp = await client.post(
        f"{api_base}/base/access_token",
        json={"username": username, "password": password},
        headers={"X-Request-Id": request_id},
    )
    finished = time.time()
    ok = resp.status_code == 200
    token = ""
    payload: dict[str, Any] = {}
    try:
        payload = resp.json()
        token = str((payload.get("data") or {}).get("access_token") or "")
    except Exception:
        token = ""
    log.step(
        "login",
        ok=ok and bool(token),
        started_at=started,
        finished_at=finished,
        request={"method": "POST", "url": f"{api_base}/base/access_token"},
        response={"status": resp.status_code, "body": payload},
    )
    if not token:
        raise RuntimeError("login_failed")
    return token


async def _list_endpoints(api_base: str, *, token: str, request_id: str, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{api_base}/llm/models",
        params={"view": "endpoints", "only_active": True, "page": 1, "page_size": 100, "debug": True},
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
    )
    resp.raise_for_status()
    return list(resp.json().get("data") or [])


async def _force_disconnect_sse(api_base: str, *, token: str, request_id: str, client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        f"{api_base}/llm/sse/force-disconnect",
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
    )
    resp.raise_for_status()
    return dict(resp.json().get("data") or {})


async def _refresh_endpoint(api_base: str, *, endpoint_id: int, token: str, request_id: str, client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        f"{api_base}/llm/models/{endpoint_id}/check",
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
    )
    resp.raise_for_status()
    return dict(resp.json().get("data") or {})


async def _upsert_mapping(
    api_base: str,
    *,
    scope_key: str,
    name: str,
    model_id: str,
    token: str,
    request_id: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    resp = await client.post(
        f"{api_base}/llm/model-groups",
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
        json={
            "scope_type": "tenant",
            "scope_key": scope_key,
            "name": name,
            "default_model": model_id,
            "candidates": [model_id],
            "is_active": True,
            "metadata": {"source": "cliproxy_models_e2e"},
        },
    )
    resp.raise_for_status()
    return dict(resp.json().get("data") or {})


async def _delete_mapping(
    api_base: str,
    *,
    mapping_id: str,
    token: str,
    request_id: str,
    client: httpx.AsyncClient,
) -> None:
    await client.delete(
        f"{api_base}/llm/model-groups/{mapping_id}",
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
    )


async def _run_messages_sse(
    api_base: str,
    *,
    model_key: str,
    token: str,
    request_id: str,
    client: httpx.AsyncClient,
    text: str,
    max_duration_s: float,
) -> tuple[bool, dict[str, Any]]:
    created = await client.post(
        f"{api_base}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Request-Id": request_id},
        json={
            "text": text,
            "model": model_key,
            "metadata": {"scenario": "cliproxy_models_e2e", "model": model_key},
            "skip_prompt": False,
        },
    )
    if created.status_code != 202:
        return False, {"stage": "create", "status": created.status_code, "body": created.text[:200]}
    payload = created.json()
    message_id = payload.get("message_id")
    conversation_id = payload.get("conversation_id")
    if not message_id or not conversation_id:
        return False, {"stage": "create", "status": created.status_code, "body": payload}

    url = f"{api_base}/messages/{message_id}/events?conversation_id={conversation_id}"
    events: list[dict[str, Any]] = []
    routed: dict[str, Any] | None = None
    completed: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    started = time.time()
    async with client.stream(
        "GET",
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "X-Request-Id": request_id,
        },
        timeout=120.0,
    ) as resp:
        if resp.status_code != 200:
            body = (await resp.aread())[:200]
            return False, {"stage": "sse", "status": resp.status_code, "body": body.decode("utf-8", errors="ignore")}

        current_event = "message"
        data_lines: list[str] = []

        def _flush() -> None:
            nonlocal current_event, data_lines, routed, completed, error
            if not data_lines:
                current_event = "message"
                return
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            events.append(_safe_sse_event(current_event, parsed))
            if current_event == "status" and isinstance(parsed, dict) and parsed.get("state") == "routed":
                routed = parsed
            if current_event == "completed" and isinstance(parsed, dict):
                completed = parsed
            if current_event == "error" and isinstance(parsed, dict):
                error = parsed
            current_event = "message"

        line_queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def _reader() -> None:
            try:
                async for raw_line in resp.aiter_lines():
                    await line_queue.put(raw_line)
            finally:
                await line_queue.put(None)

        reader_task = asyncio.create_task(_reader())
        try:
            while True:
                if time.time() - started > max_duration_s:
                    error = {
                        "message_id": message_id,
                        "error": "e2e_timeout",
                        "request_id": request_id,
                    }
                    events.append(_safe_sse_event("error", error))
                    break

                try:
                    line = await asyncio.wait_for(line_queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue

                if line is None:
                    break

                line = (line or "").rstrip("\r")
                if not line:
                    _flush()
                    if completed is not None or error is not None:
                        break
                    continue
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip() or "message"
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())
        finally:
            reader_task.cancel()
            with contextlib.suppress(BaseException):
                await reader_task

        _flush()

    ok = completed is not None and error is None and routed is not None
    summary = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "routed": routed,
        "completed": completed,
        "error": error,
        "events": events[-12:],  # 仅保留末尾少量（trace 已脱敏）
    }
    return ok, summary


@dataclass
class ModelCase:
    model_id: str
    scope_key: str
    mapping_id: str


async def main() -> int:
    request_id = uuid.uuid4().hex
    api_base = _env("E2E_API_BASE", "http://127.0.0.1:9999/api/v1").rstrip("/")
    username = _env("E2E_ADMIN_USERNAME", "admin")
    password = _env("E2E_ADMIN_PASSWORD", "123456")
    cliproxy_base_url = _env("CLIPROXY_BASE_URL", "http://172.19.32.1:8317").rstrip("/")
    max_models = int(_env("E2E_MAX_MODELS", "0") or "0")
    model_timeout_s = float(_env("E2E_MODEL_TIMEOUT_SECONDS", "45") or "45")
    filter_csv = _env("E2E_MODEL_FILTER", "")
    fail_fast = _as_bool(_env("E2E_FAIL_FAST", "0"), default=False)
    reset_sse = _as_bool(_env("E2E_RESET_SSE", "true"), default=True)
    verbose = _as_bool(_env("E2E_VERBOSE", "true"), default=True)
    output_path = _env(
        "E2E_OUTPUT_PATH",
        f"e2e/real_user_sse/artifacts/cliproxy_models_trace_{request_id}.json",
    )

    report = TraceReport(request_id=request_id, context={"api_base": api_base, "cliproxy_base_url": cliproxy_base_url})
    log = TraceLogger(report, verbose=verbose)

    wanted_models: set[str] | None = None
    if filter_csv:
        wanted_models = {s.strip() for s in filter_csv.split(",") if s.strip()}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            token = await _login(api_base, username=username, password=password, request_id=request_id, client=client, log=log)
        except Exception as exc:
            report.finished_at = time.time()
            report.write_json(Path(output_path))
            log.log(f"failed step=login error={type(exc).__name__}")
            return 2

        if reset_sse:
            started = time.time()
            try:
                stats = await _force_disconnect_sse(api_base, token=token, request_id=request_id, client=client)
                log.step(
                    "sse_force_disconnect",
                    ok=True,
                    started_at=started,
                    finished_at=time.time(),
                    response=stats,
                )
            except Exception as exc:
                log.step(
                    "sse_force_disconnect",
                    ok=False,
                    started_at=started,
                    finished_at=time.time(),
                    response={"error": str(exc)},
                )

        started = time.time()
        endpoints: list[dict[str, Any]] = []
        try:
            endpoints = await _list_endpoints(api_base, token=token, request_id=request_id, client=client)
        except Exception as exc:
            log.step(
                "list_endpoints",
                ok=False,
                started_at=started,
                finished_at=time.time(),
                response={"error": str(exc)},
            )
            report.finished_at = time.time()
            report.write_json(Path(output_path))
            return 2

        target = next((ep for ep in endpoints if str(ep.get("base_url") or "").rstrip("/") == cliproxy_base_url), None)
        if not isinstance(target, dict) or target.get("id") is None:
            log.step(
                "find_clipr",
                ok=False,
                started_at=started,
                finished_at=time.time(),
                notes={"reason": "endpoint_not_found", "hint": "请先在后台配置该 base_url 的端点与 api_key"},
            )
            report.finished_at = time.time()
            report.write_json(Path(output_path))
            return 2

        endpoint_id = int(target["id"])
        refreshed = await _refresh_endpoint(api_base, endpoint_id=endpoint_id, token=token, request_id=request_id, client=client)
        model_list = refreshed.get("model_list") if isinstance(refreshed, dict) else None
        models: list[str] = [str(x).strip() for x in (model_list or []) if isinstance(x, str) and str(x).strip()]
        if wanted_models is not None:
            models = [m for m in models if m in wanted_models]
        if max_models and max_models > 0:
            models = models[:max_models]

        log.step(
            "refresh_endpoint",
            ok=bool(models),
            started_at=started,
            finished_at=time.time(),
            notes={"endpoint_id": endpoint_id, "models_count": len(models)},
        )
        if not models:
            report.finished_at = time.time()
            report.write_json(Path(output_path))
            return 2

        cases: list[ModelCase] = []
        for model_id in models:
            digest = hashlib.sha1(model_id.encode("utf-8")).hexdigest()[:8]
            scope_key = f"clip_{_slugify(model_id, max_len=40)}_{digest}"
            mapping_id = f"tenant:{scope_key}"
            cases.append(ModelCase(model_id=model_id, scope_key=scope_key, mapping_id=mapping_id))

        failures: list[dict[str, Any]] = []
        for case in cases:
            step_started = time.time()
            mapping_id = case.mapping_id
            try:
                await _upsert_mapping(
                    api_base,
                    scope_key=case.scope_key,
                    name=f"cliproxy:{case.model_id}",
                    model_id=case.model_id,
                    token=token,
                    request_id=request_id,
                    client=client,
                )

                ok, summary = await _run_messages_sse(
                    api_base,
                    model_key=case.scope_key,
                    token=token,
                    request_id=request_id,
                    client=client,
                    text="ping",
                    max_duration_s=model_timeout_s,
                )
                log.step(
                    f"model:{case.model_id}",
                    ok=ok,
                    started_at=step_started,
                    finished_at=time.time(),
                    notes={"scope_key": case.scope_key, "endpoint_id": endpoint_id},
                    response=summary,
                )
                if not ok:
                    failures.append({"model_id": case.model_id, "scope_key": case.scope_key, "result": summary})
                    if fail_fast:
                        break
            except Exception as exc:
                failures.append({"model_id": case.model_id, "scope_key": case.scope_key, "error": str(exc)})
                log.step(
                    f"model:{case.model_id}",
                    ok=False,
                    started_at=step_started,
                    finished_at=time.time(),
                    notes={"scope_key": case.scope_key, "exception": type(exc).__name__},
                )
                if fail_fast:
                    break
            finally:
                try:
                    await _delete_mapping(api_base, mapping_id=mapping_id, token=token, request_id=request_id, client=client)
                except Exception:
                    pass

        report.finished_at = time.time()
        report.write_json(Path(output_path))
        log.log(f"done failures={len(failures)} trace={output_path}")
        return 0 if not failures else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
