#!/usr/bin/env python3
"""
Daily E2E: JWT + mapped model availability (message-only).

Flow (per user type):
1) Acquire JWT (anonymous + permanent).
2) GET /api/v1/llm/models?view=mapped (SSOT model keys).
3) For each model: POST /messages -> SSE /events until completed/error.
4) Store summary + per-model results into local SQLite.
"""

from __future__ import annotations

import argparse
import asyncio
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

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.db.sqlite_manager import SQLiteManager  # noqa: E402
from e2e.anon_jwt_sse.scripts.anon_signin_enhanced import EnhancedAnonAuth  # noqa: E402
from scripts.monitoring.local_mock_ai_conversation_e2e import _validate_thinkingml  # noqa: E402
from scripts.monitoring.real_user_ai_conversation_e2e import (  # noqa: E402
    SupabaseUser,
    _supabase_admin_create_user,
    _supabase_admin_delete_user,
    _supabase_sign_in_password,
)

REQUEST_ID_HEADER = "X-Request-Id"
DEFAULT_PROMPT_TEXT = "每日测试连通性和tools工具可用性"


def _as_bool(value: Any, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_api_base(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:9999/api/v1"
    text = text.rstrip("/")
    if text.endswith("/api/v1"):
        return text
    return text + "/api/v1"


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def _random_email(domain: str) -> str:
    suffix = uuid.uuid4().hex[:10]
    return f"daily_{suffix}@{domain}"


def _safe_error(text: str | None, limit: int = 200) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    return raw[:limit]


@dataclass
class AuthResult:
    token: Optional[str]
    mode: str
    error: Optional[str] = None
    created_user: Optional[SupabaseUser] = None


@dataclass
class ModelResult:
    model_key: str
    success: bool
    latency_ms: float
    request_id: str
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    reply_len: Optional[int] = None
    result_mode_effective: Optional[str] = None
    thinkingml_ok: Optional[bool] = None
    thinkingml_reason: Optional[str] = None
    error: Optional[str] = None


async def _fetch_dashboard_prompt_text(client: httpx.AsyncClient, token: str, fallback: str) -> str:
    if not _as_bool(os.getenv("E2E_USE_DASHBOARD_CONFIG"), False):
        return fallback
    try:
        resp = await client.get(
            "/stats/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return fallback
        data = resp.json() or {}
        payload = data.get("data") or {}
        config = payload.get("config") if isinstance(payload, dict) else None
        if isinstance(config, dict):
            text = str(config.get("e2e_prompt_text") or "").strip()
            if text:
                return text
    except Exception:
        return fallback
    return fallback


async def _get_anonymous_token(method: str) -> AuthResult:
    client = EnhancedAnonAuth()

    async def via_edge() -> str:
        data = await client.get_token_via_edge_function()
        return str(data.get("access_token") or "").strip()

    async def via_native() -> str:
        data = await client.get_token_via_native_auth()
        return str(data.get("access_token") or "").strip()

    try:
        if method == "edge":
            token = await via_edge()
            return AuthResult(token=token or None, mode="edge")
        if method == "native":
            token = await via_native()
            return AuthResult(token=token or None, mode="native")
        # auto
        try:
            token = await via_edge()
            return AuthResult(token=token or None, mode="edge")
        except Exception:
            token = await via_native()
            return AuthResult(token=token or None, mode="native")
    except Exception as exc:
        return AuthResult(token=None, mode=method, error=_safe_error(str(exc)))


async def _get_permanent_token() -> AuthResult:
    supabase_url = str(os.getenv("E2E_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").strip()
    anon_key = str(os.getenv("E2E_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
    service_role_key = str(os.getenv("E2E_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    domain = str(os.getenv("E2E_EMAIL_DOMAIN") or "example.com").strip() or "example.com"

    if not supabase_url or not anon_key:
        return AuthResult(token=None, mode="signup", error="missing_supabase_env")

    created_user: SupabaseUser | None = None
    password = str(os.getenv("E2E_USER_PASSWORD") or os.getenv("TEST_USER_PASSWORD") or "").strip()
    if not password:
        password = "TestPassword123!"

    try:
        if service_role_key:
            email = _random_email(domain)
            created_user = await _supabase_admin_create_user(
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                email=email,
                password=password,
            )
            token = await _supabase_sign_in_password(
                supabase_url=supabase_url,
                anon_key=anon_key,
                email=created_user.email,
                password=created_user.password,
            )
            return AuthResult(token=token, mode="signup", created_user=created_user)

        email = str(os.getenv("E2E_USER_EMAIL") or os.getenv("TEST_USER_EMAIL") or "").strip()
        if not email:
            return AuthResult(token=None, mode="password", error="missing_user_credentials")
        token = await _supabase_sign_in_password(
            supabase_url=supabase_url,
            anon_key=anon_key,
            email=email,
            password=password,
        )
        return AuthResult(token=token, mode="password")
    except Exception as exc:
        return AuthResult(token=None, mode="signup", error=_safe_error(str(exc)), created_user=created_user)


async def _fetch_mapped_models(client: httpx.AsyncClient, token: str) -> list[str]:
    resp = await client.get(
        "/llm/models",
        params={"view": "mapped"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"fetch_models_failed: HTTP {resp.status_code}")
    payload = _unwrap_data(resp.json())
    if not isinstance(payload, list):
        return []
    keys: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if name:
            keys.append(name)
    # de-dup while preserving order
    seen: set[str] = set()
    uniq = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    return uniq


async def _create_message(
    client: httpx.AsyncClient,
    *,
    token: str,
    model_key: str,
    text: str,
    result_mode: Optional[str],
    request_id: str,
    metadata: dict[str, Any],
) -> tuple[str, str]:
    payload: dict[str, Any] = {
        "text": text.strip(),
        "model": model_key,
        "metadata": metadata,
        "skip_prompt": False,
    }
    if result_mode:
        payload["result_mode"] = result_mode
    resp = await client.post(
        "/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            REQUEST_ID_HEADER: request_id,
        },
        json=payload,
        timeout=30.0,
    )
    if resp.status_code != 202:
        raise RuntimeError(f"messages_create_failed: HTTP {resp.status_code}")
    data = resp.json() or {}
    message_id = str(data.get("message_id") or "").strip()
    conversation_id = str(data.get("conversation_id") or "").strip()
    if not message_id or not conversation_id:
        raise RuntimeError("messages_response_missing_ids")
    return message_id, conversation_id


async def _consume_sse(
    client: httpx.AsyncClient,
    *,
    token: str,
    message_id: str,
    conversation_id: str,
    request_id: str,
    stream_timeout: float,
    max_events: int,
) -> tuple[bool, str, Optional[str], Optional[str]]:
    url = f"/messages/{message_id}/events"
    params = {"conversation_id": conversation_id}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        REQUEST_ID_HEADER: request_id,
    }
    reply = ""
    result_mode_effective: Optional[str] = None
    event_name: Optional[str] = None
    events_seen = 0

    async with client.stream("GET", url, params=params, headers=headers, timeout=stream_timeout) as resp:
        if resp.status_code != 200:
            return False, "", None, f"sse_connect_failed:{resp.status_code}"
        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
                continue
            if not line.startswith("data:"):
                continue
            raw = line[len("data:") :].strip()
            if raw == "[DONE]":
                break
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                continue

            events_seen += 1
            if events_seen > max_events:
                return False, reply, result_mode_effective, "sse_max_events_exceeded"

            if event_name == "content_delta":
                delta = str(data.get("delta") or "")
                reply += delta
                continue
            if event_name == "completed":
                result_mode_effective = str(data.get("result_mode_effective") or data.get("result_mode") or "").strip() or None
                if not reply:
                    reply = str(data.get("reply") or "")
                return True, reply, result_mode_effective, None
            if event_name == "error":
                err = str(data.get("error") or data.get("message") or "sse_error")
                return False, reply, result_mode_effective, err

    return False, reply, result_mode_effective, "sse_stream_incomplete"


async def _run_for_user(
    *,
    api_base: str,
    user_type: str,
    token: str,
    prompt_text: str,
    result_mode: Optional[str],
    models_override: Optional[list[str]],
    stream_timeout: float,
    max_events: int,
) -> tuple[dict[str, Any], list[ModelResult]]:
    started_at = time.perf_counter()
    started_iso = _iso_now()
    results: list[ModelResult] = []
    error_summary = ""

    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
        if models_override:
            model_keys = models_override
        else:
            model_keys = await _fetch_mapped_models(client, token)
        if not model_keys:
            error_summary = "no_mapped_models"
        for model_key in model_keys:
            request_id = uuid.uuid4().hex
            model_start = time.perf_counter()
            try:
                message_id, conversation_id = await _create_message(
                    client,
                    token=token,
                    model_key=model_key,
                    text=prompt_text,
                    result_mode=result_mode,
                    request_id=request_id,
                    metadata={
                        "source": "daily_e2e",
                        "e2e": True,
                        "user_type": user_type,
                    },
                )
                sse_ok, reply_text, effective_mode, err = await _consume_sse(
                    client,
                    token=token,
                    message_id=message_id,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    stream_timeout=stream_timeout,
                    max_events=max_events,
                )
                latency_ms = round((time.perf_counter() - model_start) * 1000.0, 2)
                reply_len = len(reply_text or "")

                thinkingml_ok: bool | None = None
                thinkingml_reason: str | None = None
                validate_thinkingml = _as_bool(os.getenv("E2E_VALIDATE_THINKINGML"), default=True)
                if sse_ok and validate_thinkingml:
                    mode_for_validation = str(effective_mode or result_mode or "").strip()
                    if mode_for_validation == "xml_plaintext":
                        thinkingml_ok, thinkingml_reason = _validate_thinkingml(reply_text)

                ok = bool(sse_ok) and (bool(thinkingml_ok) if thinkingml_ok is not None else True)

                if sse_ok and thinkingml_ok is False and not err:
                    err = f"thinkingml:{thinkingml_reason or 'invalid'}"
                results.append(
                    ModelResult(
                        model_key=model_key,
                        success=ok,
                        latency_ms=latency_ms,
                        request_id=request_id,
                        message_id=message_id,
                        conversation_id=conversation_id,
                        reply_len=reply_len,
                        result_mode_effective=effective_mode,
                        error=_safe_error(err),
                        thinkingml_ok=thinkingml_ok,
                        thinkingml_reason=thinkingml_reason,
                    )
                )
            except Exception as exc:
                latency_ms = round((time.perf_counter() - model_start) * 1000.0, 2)
                results.append(
                    ModelResult(
                        model_key=model_key,
                        success=False,
                        latency_ms=latency_ms,
                        request_id=request_id,
                        error=_safe_error(str(exc)),
                    )
                )

    total = len(results)
    success = sum(1 for item in results if item.success)
    failed = total - success
    status = "success" if total > 0 and failed == 0 else "failed"
    if not total and not error_summary:
        error_summary = "no_results"

    run = {
        "run_id": uuid.uuid4().hex,
        "user_type": user_type,
        "prompt_text": prompt_text,
        "prompt_mode": "server",
        "result_mode": result_mode,
        "models_total": total,
        "models_success": success,
        "models_failed": failed,
        "started_at": started_iso,
        "finished_at": _iso_now(),
        "duration_ms": round((time.perf_counter() - started_at) * 1000.0, 2),
        "status": status,
        "error_summary": error_summary,
    }
    return run, results


async def _persist_run(db_path: Path, run: dict[str, Any], results: list[ModelResult], auth_mode: str) -> None:
    db = SQLiteManager(db_path)
    await db.init()

    serialized = [
        {
            "model_key": item.model_key,
            "success": item.success,
            "latency_ms": item.latency_ms,
            "request_id": item.request_id,
            "message_id": item.message_id,
            "conversation_id": item.conversation_id,
            "reply_len": item.reply_len,
            "result_mode_effective": item.result_mode_effective,
            "thinkingml_ok": item.thinkingml_ok,
            "thinkingml_reason": item.thinkingml_reason,
            "error": item.error,
        }
        for item in results
    ]

    await db.execute(
        """
        INSERT INTO e2e_mapped_model_runs
        (run_id, user_type, auth_mode, prompt_text, prompt_mode, result_mode,
         models_total, models_success, models_failed, started_at, finished_at,
         duration_ms, status, error_summary, results_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.get("run_id"),
            run.get("user_type"),
            auth_mode,
            run.get("prompt_text"),
            run.get("prompt_mode"),
            run.get("result_mode"),
            run.get("models_total"),
            run.get("models_success"),
            run.get("models_failed"),
            run.get("started_at"),
            run.get("finished_at"),
            run.get("duration_ms"),
            run.get("status"),
            run.get("error_summary"),
            json.dumps(serialized, ensure_ascii=False),
        ),
    )
    await db.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily mapped-model JWT E2E (message-only)")
    parser.add_argument("--api-base", default=os.getenv("E2E_API_BASE", os.getenv("API_BASE", "")))
    parser.add_argument("--prompt-text", default=os.getenv("E2E_DAILY_PROMPT_TEXT", os.getenv("E2E_MESSAGE_TEXT", "")))
    parser.add_argument("--result-mode", default=os.getenv("E2E_RESULT_MODE", ""))
    parser.add_argument("--models", nargs="*", default=None, help="可选：仅测试指定映射模型 key")
    parser.add_argument("--stream-timeout", type=float, default=float(os.getenv("E2E_STREAM_TIMEOUT", "120")))
    parser.add_argument("--max-events", type=int, default=_as_int(os.getenv("E2E_MAX_EVENTS", 4000), 4000))
    parser.add_argument("--sqlite-path", default=os.getenv("SQLITE_DB_PATH", "data/db.sqlite3"))
    parser.add_argument("--anon-method", choices=["auto", "edge", "native"], default=os.getenv("E2E_ANON_METHOD", "auto"))
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    api_base = _normalize_api_base(args.api_base)
    prompt_text = str(args.prompt_text or "").strip() or DEFAULT_PROMPT_TEXT
    result_mode = str(args.result_mode or "").strip() or None
    db_path = Path(str(args.sqlite_path or "data/db.sqlite3"))

    # Anonymous auth
    anon_auth = await _get_anonymous_token(args.anon_method)

    # Permanent auth
    perm_auth = await _get_permanent_token()

    overall_ok = True

    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
        if perm_auth.token:
            prompt_text = await _fetch_dashboard_prompt_text(client, perm_auth.token, prompt_text)
        elif anon_auth.token:
            prompt_text = await _fetch_dashboard_prompt_text(client, anon_auth.token, prompt_text)

    # Anonymous run
    if anon_auth.token:
        run, results = await _run_for_user(
            api_base=api_base,
            user_type="anonymous",
            token=anon_auth.token,
            prompt_text=prompt_text,
            result_mode=result_mode,
            models_override=args.models,
            stream_timeout=float(args.stream_timeout),
            max_events=int(args.max_events),
        )
        await _persist_run(db_path, run, results, anon_auth.mode)
        if run.get("status") != "success":
            overall_ok = False
    else:
        fail_run = {
            "run_id": uuid.uuid4().hex,
            "user_type": "anonymous",
            "prompt_text": prompt_text,
            "prompt_mode": "server",
            "result_mode": result_mode,
            "models_total": 0,
            "models_success": 0,
            "models_failed": 0,
            "started_at": _iso_now(),
            "finished_at": _iso_now(),
            "duration_ms": 0.0,
            "status": "failed",
            "error_summary": anon_auth.error or "anonymous_auth_failed",
        }
        await _persist_run(db_path, fail_run, [], anon_auth.mode or "auto")
        overall_ok = False

    # Permanent run
    if perm_auth.token:
        run, results = await _run_for_user(
            api_base=api_base,
            user_type="permanent",
            token=perm_auth.token,
            prompt_text=prompt_text,
            result_mode=result_mode,
            models_override=args.models,
            stream_timeout=float(args.stream_timeout),
            max_events=int(args.max_events),
        )
        await _persist_run(db_path, run, results, perm_auth.mode)
        if run.get("status") != "success":
            overall_ok = False
    else:
        fail_run = {
            "run_id": uuid.uuid4().hex,
            "user_type": "permanent",
            "prompt_text": prompt_text,
            "prompt_mode": "server",
            "result_mode": result_mode,
            "models_total": 0,
            "models_success": 0,
            "models_failed": 0,
            "started_at": _iso_now(),
            "finished_at": _iso_now(),
            "duration_ms": 0.0,
            "status": "failed",
            "error_summary": perm_auth.error or "permanent_auth_failed",
        }
        await _persist_run(db_path, fail_run, [], perm_auth.mode or "signup")
        overall_ok = False

    cleanup = _as_bool(os.getenv("E2E_CLEANUP_USER"), True)
    supabase_url = str(os.getenv("E2E_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").strip()
    service_role_key = str(os.getenv("E2E_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if cleanup and perm_auth.created_user and supabase_url and service_role_key:
        try:
            await _supabase_admin_delete_user(
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                user_id=perm_auth.created_user.user_id,
            )
        except Exception:
            pass

    return 0 if overall_ok else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
