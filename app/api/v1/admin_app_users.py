"""Admin: manage App users (SSOT: Supabase auth.users + entitlements/auth-admin actions)."""

from __future__ import annotations

import secrets
import string
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.dashboard_deps import require_dashboard_capability_user
from app.auth import AuthenticatedUser
from app.auth.dashboard_access import CAP_APP_USERS_MANAGE
from app.core.middleware import get_current_request_id
from app.db import get_sqlite_manager
from app.services.supabase_admin import SupabaseAdminClient
from app.services.supabase_auth_admin import SupabaseAuthAdminClient

from .llm_common import create_response

router = APIRouter(prefix="/admin", tags=["app-users-admin"])

require_dashboard_admin = require_dashboard_capability_user(CAP_APP_USERS_MANAGE, msg="Admin privileges required")


def _get_supabase_admin(request: Request) -> SupabaseAdminClient:
    client = getattr(request.app.state, "supabase_admin", None)
    if not isinstance(client, SupabaseAdminClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(
                code=503,
                msg="Supabase 未配置：需要 SUPABASE_URL(或 SUPABASE_PROJECT_ID) + SUPABASE_SERVICE_ROLE_KEY",
            ),
        )
    return client


def _get_supabase_auth_admin(request: Request) -> SupabaseAuthAdminClient:
    client = getattr(request.app.state, "supabase_auth_admin", None)
    # 允许测试注入 mock（duck-typing），避免对运行时 SSOT（SupabaseAuthAdminClient）造成耦合。
    if not isinstance(client, SupabaseAuthAdminClient) and not (
        hasattr(client, "get_user") and hasattr(client, "update_user")
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(
                code=503,
                msg="Supabase 未配置：需要 SUPABASE_URL(或 SUPABASE_PROJECT_ID) + SUPABASE_SERVICE_ROLE_KEY（Auth Admin）",
            ),
        )
    return client  # type: ignore[return-value]


_DEFAULT_APP_USER_ADMIN_CONFIG: dict[str, Any] = {
    "default_page_size": 20,
    "default_include_anonymous": False,
    "default_active_only": True,
    "allow_edit_entitlements": True,
    "allow_manage_permissions": True,
    "allow_disable_user": True,
    "allow_reset_password": False,
    "require_confirm_user_id_for_dangerous_actions": True,
    "reset_password_length": 16,
}

_DEFAULT_TIER_PRESETS: dict[str, dict[str, Any]] = {
    "free": {"tier": "free", "default_expires_days": None, "flags": {}},
    "pro": {"tier": "pro", "default_expires_days": 30, "flags": {}},
}


def _normalize_tier(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_flags_json(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


async def _list_effective_tier_presets(request: Request) -> list[dict[str, Any]]:
    db = get_sqlite_manager(request.app)
    rows = await db.fetchall(
        "SELECT tier, default_expires_days, default_flags_json FROM user_entitlement_tier_presets ORDER BY tier ASC",
        (),
    )

    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in _DEFAULT_TIER_PRESETS.items()}
    for row in rows:
        tier = _normalize_tier(row.get("tier"))
        if not tier or tier == "other":
            continue
        merged[tier] = {
            "tier": tier,
            "default_expires_days": (int(row["default_expires_days"]) if row.get("default_expires_days") is not None else None),
            "flags": _parse_flags_json(row.get("default_flags_json")),
        }

    ordered: list[dict[str, Any]] = []
    for fixed in ("free", "pro"):
        if fixed in merged:
            ordered.append(merged[fixed])
    for tier in sorted(t for t in merged.keys() if t not in {"free", "pro"}):
        ordered.append(merged[tier])
    return ordered


async def _get_app_user_admin_config(request: Request) -> dict[str, Any]:
    db = get_sqlite_manager(request.app)
    rows = await db.fetchall(
        "SELECT key, value_json FROM app_user_admin_settings ORDER BY key ASC",
        (),
    )
    merged = dict(_DEFAULT_APP_USER_ADMIN_CONFIG)
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        raw = row.get("value_json")
        if raw is None:
            continue
        try:
            merged[key] = json.loads(str(raw))
        except Exception:
            # Best-effort: allow non-JSON legacy values
            merged[key] = raw

    # normalize
    merged["default_page_size"] = int(merged.get("default_page_size") or 20)
    merged["default_include_anonymous"] = bool(merged.get("default_include_anonymous", False))
    merged["default_active_only"] = bool(merged.get("default_active_only", True))
    merged["allow_edit_entitlements"] = bool(merged.get("allow_edit_entitlements", True))
    merged["allow_manage_permissions"] = bool(merged.get("allow_manage_permissions", True))
    merged["allow_disable_user"] = bool(merged.get("allow_disable_user", True))
    merged["allow_reset_password"] = bool(merged.get("allow_reset_password", False))
    merged["require_confirm_user_id_for_dangerous_actions"] = bool(
        merged.get("require_confirm_user_id_for_dangerous_actions", True)
    )
    merged["reset_password_length"] = max(int(merged.get("reset_password_length") or 16), 8)
    return merged


async def _set_app_user_admin_config(request: Request, values: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = set(_DEFAULT_APP_USER_ADMIN_CONFIG.keys())
    db = get_sqlite_manager(request.app)
    for key, value in values.items():
        if key not in allowed_keys:
            continue
        try:
            value_json = json.dumps(value, ensure_ascii=False)
        except Exception:
            value_json = json.dumps(str(value), ensure_ascii=False)
        await db.execute(
            """
            INSERT INTO app_user_admin_settings(key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
              value_json = excluded.value_json,
              updated_at = CURRENT_TIMESTAMP
            """,
            (str(key), value_json),
        )
    return await _get_app_user_admin_config(request)


def _build_in_filter(values: list[str]) -> Optional[str]:
    cleaned: list[str] = []
    for v in values:
        text = str(v or "").strip()
        if not text:
            continue
        cleaned.append(text)
    if not cleaned:
        return None
    # PostgREST: in.(a,b,c) - UUIDs do not require quoting
    return f"in.({','.join(cleaned)})"


async def _fetch_app_users_list_payload(
    request: Request,
    *,
    page: int,
    page_size: int,
    keyword: Optional[str],
    user_id: Optional[str],
    active_only: Optional[bool],
    include_anonymous: Optional[bool],
) -> dict[str, Any]:
    """Fetch app user list payload (best-effort, prefer auth.users-based view)."""
    config = await _get_app_user_admin_config(request)

    effective_active_only = bool(config.get("default_active_only", True)) if active_only is None else bool(active_only)
    effective_include_anon = (
        bool(config.get("default_include_anonymous", False)) if include_anonymous is None else bool(include_anonymous)
    )

    limit = int(page_size)
    offset = (int(page) - 1) * limit

    # Fast path: view includes entitlements + auth fields and avoids orphan public.users rows.
    supabase = getattr(request.app.state, "supabase_admin", None)
    if isinstance(supabase, SupabaseAdminClient):
        filters: dict[str, Any] = {}
        if user_id:
            filters["user_id"] = f"eq.{str(user_id).strip()}"
        if effective_active_only:
            filters["is_active"] = "eq.true"
        if not effective_include_anon:
            filters["is_anonymous"] = "eq.false"
        if keyword and str(keyword).strip():
            q = str(keyword).strip()
            filters["or"] = f"(email.ilike.*{q}*,username.ilike.*{q}*)"

        try:
            rows, total = await supabase.fetch_list(
                table="app_users_admin_view",
                filters=filters or None,
                select="user_id,email,username,is_anonymous,is_active,last_sign_in_at,created_at,banned_until,tier,expires_at,flags,last_updated,entitlements_exists",
                order="last_sign_in_at.desc",
                limit=limit,
                offset=offset,
                with_count=True,
            )
            items: list[dict[str, Any]] = []
            for row in rows:
                items.append(
                    {
                        "user_id": row.get("user_id"),
                        "email": row.get("email"),
                        "username": row.get("username"),
                        # frontend-compatible numeric flags
                        "isanonymous": 1 if bool(row.get("is_anonymous")) else 0,
                        "isactive": 1 if bool(row.get("is_active")) else 0,
                        "last_sign_in_at": row.get("last_sign_in_at"),
                        "created_at": row.get("created_at"),
                        "banned_until": row.get("banned_until"),
                        "tier": row.get("tier") or "free",
                        "expires_at": row.get("expires_at"),
                        "flags": row.get("flags") if isinstance(row.get("flags"), dict) else {},
                        "last_updated": row.get("last_updated"),
                        "entitlements_exists": bool(row.get("entitlements_exists")),
                    }
                )

            return {
                "items": items,
                "total": int(total if total is not None else len(items)),
                "page": int(page),
                "page_size": int(page_size),
                "effective_filters": {"active_only": effective_active_only, "include_anonymous": effective_include_anon},
            }
        except Exception:
            # fall back to legacy public.users list below
            pass

    # Fallback: legacy public.users list (may contain orphan rows, no auth fields).
    supabase = _get_supabase_admin(request)
    legacy_filters: dict[str, Any] = {}
    if user_id:
        legacy_filters["user_id"] = f"eq.{str(user_id).strip()}"
    if effective_active_only:
        legacy_filters["isactive"] = "eq.1"
    if not effective_include_anon:
        legacy_filters["isanonymous"] = "eq.0"
    if keyword and str(keyword).strip():
        q = str(keyword).strip()
        legacy_filters["or"] = f"(email.ilike.*{q}*,username.ilike.*{q}*)"

    users, total = await supabase.fetch_list(
        table="users",
        filters=legacy_filters or None,
        select="user_id,email,username,displayname,isanonymous,isactive,lastloginat,createdat,subscriptionexpirydate",
        order="lastloginat.desc",
        limit=limit,
        offset=offset,
        with_count=True,
    )

    user_ids = [str(item.get("user_id") or "").strip() for item in users if str(item.get("user_id") or "").strip()]
    entitlements_by_uid: dict[str, dict[str, Any]] = {}
    in_filter = _build_in_filter(user_ids)
    if in_filter:
        ent_rows, _ = await supabase.fetch_list(
            table="user_entitlements",
            filters={"user_id": in_filter},
            select="user_id,tier,expires_at,flags,last_updated",
            order=None,
            limit=max(len(user_ids), 1),
            offset=0,
            with_count=False,
        )
        for row in ent_rows:
            uid = str(row.get("user_id") or "").strip()
            if uid:
                entitlements_by_uid[uid] = row

    merged_items: list[dict[str, Any]] = []
    for item in users:
        uid = str(item.get("user_id") or "").strip()
        ent = entitlements_by_uid.get(uid) if uid else None
        merged_items.append(
            {
                **item,
                "tier": str((ent or {}).get("tier") or "free"),
                "expires_at": (ent or {}).get("expires_at"),
                "flags": (ent or {}).get("flags") if isinstance((ent or {}).get("flags"), dict) else {},
                "entitlements_exists": bool(ent),
            }
        )

    return {
        "items": merged_items,
        "total": int(total if total is not None else len(merged_items)),
        "page": int(page),
        "page_size": int(page_size),
        "effective_filters": {"active_only": effective_active_only, "include_anonymous": effective_include_anon},
    }


async def _write_audit_log(
    request: Request,
    *,
    admin_user: AuthenticatedUser,
    action: str,
    resource: str,
    resource_id: str,
    details: dict[str, Any],
    status_text: str = "ok",
) -> bool:
    supabase = _get_supabase_admin(request)
    values = {
        "action": str(action),
        "resource": str(resource),
        "resource_id": str(resource_id),
        "user_id": str(admin_user.uid),
        "details": details,
        "status": status_text,
        "is_anonymous": False,
    }
    try:
        await supabase.upsert_one(table="audit_logs", values=values, on_conflict="id")
        return True
    except Exception:
        return False


def _generate_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    # avoid ambiguous chars
    alphabet = alphabet.replace("O", "").replace("0", "").replace("l", "").replace("I", "")
    return "".join(secrets.choice(alphabet) for _ in range(max(int(length), 8)))


@router.get("/app-users/config", response_model=None)
async def get_app_user_admin_config(
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    data = await _get_app_user_admin_config(request)
    return create_response(data=data, msg="ok")


class AppUserAdminConfigUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_page_size: int | None = Field(default=None, ge=1, le=100)
    default_include_anonymous: bool | None = None
    default_active_only: bool | None = None
    allow_edit_entitlements: bool | None = None
    allow_manage_permissions: bool | None = None
    allow_disable_user: bool | None = None
    allow_reset_password: bool | None = None
    require_confirm_user_id_for_dangerous_actions: bool | None = None
    reset_password_length: int | None = Field(default=None, ge=8, le=64)


@router.post("/app-users/config", response_model=None)
async def upsert_app_user_admin_config(
    payload: AppUserAdminConfigUpsertRequest,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    data = await _set_app_user_admin_config(request, values)
    return create_response(data=data, msg="updated")


async def _compute_app_users_stats_payload(request: Request) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)
    now_ms = int(time.time() * 1000)

    # Prefer SSOT view (auth.users based) to avoid counting orphan public.users rows.
    try:
        total_users = int(await supabase.count_rows(table="app_users_admin_view"))
        anonymous_users = int(await supabase.count_rows(table="app_users_admin_view", filters={"is_anonymous": "eq.true"}))
        active_users = int(await supabase.count_rows(table="app_users_admin_view", filters={"is_active": "eq.true"}))
    except Exception:
        total_users = int(await supabase.count_rows(table="users"))
        try:
            anonymous_users = int(await supabase.count_rows(table="users", filters={"isanonymous": "eq.1"}))
        except Exception:
            anonymous_users = 0
        try:
            active_users = int(await supabase.count_rows(table="users", filters={"isactive": "eq.1"}))
        except Exception:
            active_users = 0

    return {
        "server_time_ms": now_ms,
        "total_users": int(total_users),
        "anonymous_users": int(anonymous_users),
        "permanent_users": max(int(total_users) - int(anonymous_users), 0),
        "active_users": int(active_users),
    }


@router.get("/app-users/stats", response_model=None)
async def get_app_users_stats(
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    data = await _compute_app_users_stats_payload(request)
    return create_response(data=data, msg="ok")


@router.get("/app-users/bootstrap", response_model=None)
async def get_app_users_bootstrap(
    request: Request,
    page: int = Query(1, ge=1, le=100000, description="1-based page number"),  # noqa: B008
    page_size: int = Query(0, ge=0, le=100, description="0 means use configured default"),  # noqa: B008
    keyword: str | None = Query(None, description="Search by email/username (ILIKE)"),  # noqa: B008
    user_id: str | None = Query(None, description="Filter by user_id (UUID string)"),  # noqa: B008
    active_only: bool | None = Query(None, description="Only active users"),  # noqa: B008
    include_anonymous: bool | None = Query(None, description="Include anonymous users"),  # noqa: B008
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    presets = await _list_effective_tier_presets(request)

    # Best-effort readiness probe (do not fail the endpoint).
    supabase_ready = False
    supabase_hint = None
    try:
        supabase = _get_supabase_admin(request)
        await supabase.fetch_list(
            table="app_users_admin_view",
            filters=None,
            select="user_id",
            order=None,
            limit=1,
            offset=0,
            with_count=False,
        )
        supabase_ready = True
    except Exception:
        supabase_ready = False
        supabase_hint = "Supabase 未就绪或缺少视图 app_users_admin_view"

    # stats (best-effort)
    stats_payload: dict[str, Any] = {
        "server_time_ms": int(time.time() * 1000),
        "total_users": 0,
        "anonymous_users": 0,
        "permanent_users": 0,
        "active_users": 0,
    }
    try:
        stats_payload = await _compute_app_users_stats_payload(request)
    except Exception:
        stats_payload = stats_payload

    effective_page_size = int(page_size) if int(page_size) > 0 else int(config.get("default_page_size") or 20)
    list_payload: dict[str, Any] = {"items": [], "total": 0, "page": int(page), "page_size": int(effective_page_size), "effective_filters": {}}
    try:
        list_payload = await _fetch_app_users_list_payload(
            request,
            page=int(page),
            page_size=int(effective_page_size),
            keyword=keyword,
            user_id=user_id,
            active_only=active_only,
            include_anonymous=include_anonymous,
        )
    except Exception:
        list_payload = list_payload

    data = {
        "config": config,
        "tier_presets": presets,
        "stats": stats_payload,
        "supabase_ready": bool(supabase_ready),
        "supabase_hint": supabase_hint,
        "list": list_payload,
    }
    return create_response(data=data, msg="ok")


@router.get("/app-users/list", response_model=None)
async def list_app_users(
    request: Request,
    page: int = Query(1, ge=1, le=100000, description="1-based page number"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    keyword: str | None = Query(None, description="Search by email/username (ILIKE)"),  # noqa: B008
    user_id: str | None = Query(None, description="Filter by user_id (UUID string)"),  # noqa: B008
    active_only: bool | None = Query(None, description="Only active users"),  # noqa: B008
    include_anonymous: bool | None = Query(None, description="Include anonymous users"),  # noqa: B008
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    payload = await _fetch_app_users_list_payload(
        request,
        page=int(page),
        page_size=int(page_size),
        keyword=keyword,
        user_id=user_id,
        active_only=active_only,
        include_anonymous=include_anonymous,
    )
    return create_response(data=payload, msg="ok")


@router.get("/app-users/{user_id}", response_model=None)
async def get_app_user_snapshot(
    user_id: str,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)
    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    auth_user = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    entitlements = await supabase.fetch_one_by_user_id(table="user_entitlements", user_id=user_id)

    data = {
        "user_id": user_id,
        "auth_user": auth_user,
        "entitlements": entitlements,
    }
    return create_response(data=data, msg="ok")


class AppUserEntitlementsUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str = Field(..., min_length=1)
    expires_at: int | None = Field(default=None, ge=0)
    flags: dict[str, Any] = Field(default_factory=dict)


@router.post("/app-users/{user_id}/entitlements", response_model=None)
async def upsert_app_user_entitlements(
    user_id: str,
    payload: AppUserEntitlementsUpsertRequest,
    request: Request,
    admin_user: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    if not bool(config.get("allow_edit_entitlements", True)):
        return create_response(code=403, msg="已禁用订阅编辑（配置）", data={"error": "edit_entitlements_disabled_by_config"})

    supabase = _get_supabase_admin(request)
    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()
    auth_user = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    if auth_user is None:
        return create_response(
            code=400,
            msg="用户不存在或已被删除",
            data={"user_id": user_id, "error": "auth_user_not_found"},
        )
    now_ms = int(time.time() * 1000)

    values: dict[str, Any] = {
        "user_id": user_id,
        "tier": payload.tier,
        "expires_at": payload.expires_at,
        "flags": payload.flags,
        "last_updated": now_ms,
    }
    row = await supabase.upsert_one(table="user_entitlements", values=values, on_conflict="user_id")
    audit_ok = await _write_audit_log(
        request,
        admin_user=admin_user,
        action="upsert_entitlements",
        resource="app_user",
        resource_id=user_id,
        details={"tier": payload.tier, "expires_at": payload.expires_at, "flags_keys": sorted(list(payload.flags.keys()))},
    )

    return create_response(data={"entitlements": row, "audit_ok": audit_ok}, msg="updated")


class AppUserPermissionsUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, description="App role (stored in auth.users app_metadata)")
    permissions: Any | None = Field(default=None, description="Permissions payload (stored in auth.users app_metadata)")


@router.post("/app-users/{user_id}/permissions", response_model=None)
async def upsert_app_user_permissions(
    user_id: str,
    payload: AppUserPermissionsUpsertRequest,
    request: Request,
    admin_user: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    if not bool(config.get("allow_manage_permissions", True)):
        return create_response(code=403, msg="已禁用权限管理（配置）", data={"error": "manage_permissions_disabled_by_config"})

    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    existing = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    existing_app_meta = (existing or {}).get("app_metadata")
    app_meta: dict[str, Any] = dict(existing_app_meta) if isinstance(existing_app_meta, dict) else {}

    if payload.role is not None:
        app_meta["app_role"] = str(payload.role).strip()
    if payload.permissions is not None:
        app_meta["app_permissions"] = payload.permissions

    updated = await auth_admin.update_user(user_id=user_id, app_metadata=app_meta, request_id=request_id)
    audit_ok = await _write_audit_log(
        request,
        admin_user=admin_user,
        action="upsert_permissions",
        resource="app_user",
        resource_id=user_id,
        details={"app_role": app_meta.get("app_role"), "permissions_type": type(app_meta.get("app_permissions")).__name__},
    )
    return create_response(data={"auth_user": updated, "audit_ok": audit_ok}, msg="updated")


class DangerousActionConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str | None = Field(default=None, description="Confirm text (user_id or email)")
    confirm_user_id: str | None = Field(default=None, description="Legacy: must equal path user_id when required")
    reason: str | None = Field(default=None, description="Optional audit reason")


def _matches_confirm_text(*, user_id: str, auth_user: Optional[dict[str, Any]], payload: DangerousActionConfirmRequest) -> bool:
    expected_user_id = str(user_id).strip()
    text = str(payload.confirm_user_id or payload.confirm or "").strip()
    if not text:
        return False
    if text == expected_user_id:
        return True
    email = None
    if isinstance(auth_user, dict):
        email = auth_user.get("email")
    if isinstance(email, str) and email.strip():
        return text.lower() == email.strip().lower()
    return False


@router.post("/app-users/{user_id}/disable", response_model=None)
async def disable_app_user(
    user_id: str,
    payload: DangerousActionConfirmRequest,
    request: Request,
    admin_user: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    if not bool(config.get("allow_disable_user", True)):
        return create_response(code=403, msg="已禁用该操作（配置）", data={"error": "disable_user_disabled_by_config"})

    supabase = _get_supabase_admin(request)
    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()
    auth_user = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    require_confirm = bool(config.get("require_confirm_user_id_for_dangerous_actions", True))
    if require_confirm and not _matches_confirm_text(user_id=user_id, auth_user=auth_user, payload=payload):
        return create_response(code=400, msg="二次确认不匹配", data={"error": "confirm_mismatch"})
    banned_until = datetime.now(timezone.utc) + timedelta(days=3650)
    updated = await auth_admin.update_user(user_id=user_id, banned_until=banned_until, request_id=request_id)
    public_updated = None
    try:
        public_updated = await supabase.update_one_by_user_id(table="users", user_id=user_id, values={"isactive": 0})
    except Exception:
        public_updated = None
    audit_ok = await _write_audit_log(
        request,
        admin_user=admin_user,
        action="disable_user",
        resource="app_user",
        resource_id=user_id,
        details={
            "reason": (payload.reason or "").strip(),
            "banned_until": banned_until.isoformat(),
            "public_isactive": 0,
        },
    )
    return create_response(data={"auth_user": updated, "public_user": public_updated, "audit_ok": audit_ok}, msg="disabled")


@router.post("/app-users/{user_id}/enable", response_model=None)
async def enable_app_user(
    user_id: str,
    payload: DangerousActionConfirmRequest,
    request: Request,
    admin_user: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    if not bool(config.get("allow_disable_user", True)):
        return create_response(code=403, msg="已禁用该操作（配置）", data={"error": "enable_user_disabled_by_config"})

    supabase = _get_supabase_admin(request)
    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()
    auth_user = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    require_confirm = bool(config.get("require_confirm_user_id_for_dangerous_actions", True))
    if require_confirm and not _matches_confirm_text(user_id=user_id, auth_user=auth_user, payload=payload):
        return create_response(code=400, msg="二次确认不匹配", data={"error": "confirm_mismatch"})
    updated = await auth_admin.update_user(user_id=user_id, clear_banned_until=True, request_id=request_id)
    public_updated = None
    try:
        public_updated = await supabase.update_one_by_user_id(table="users", user_id=user_id, values={"isactive": 1})
    except Exception:
        public_updated = None
    audit_ok = await _write_audit_log(
        request,
        admin_user=admin_user,
        action="enable_user",
        resource="app_user",
        resource_id=user_id,
        details={"reason": (payload.reason or "").strip(), "public_isactive": 1},
    )
    return create_response(data={"auth_user": updated, "public_user": public_updated, "audit_ok": audit_ok}, msg="enabled")


@router.post("/app-users/{user_id}/reset-password", response_model=None)
async def reset_app_user_password(
    user_id: str,
    payload: DangerousActionConfirmRequest,
    request: Request,
    admin_user: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    config = await _get_app_user_admin_config(request)
    if not bool(config.get("allow_reset_password", False)):
        return create_response(code=403, msg="已禁用重置密码（配置）", data={"error": "reset_password_disabled_by_config"})

    password = _generate_password(int(config.get("reset_password_length") or 16))
    auth_admin = _get_supabase_auth_admin(request)
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()
    auth_user = await auth_admin.get_user(user_id=user_id, request_id=request_id)
    require_confirm = bool(config.get("require_confirm_user_id_for_dangerous_actions", True))
    if require_confirm and not _matches_confirm_text(user_id=user_id, auth_user=auth_user, payload=payload):
        return create_response(code=400, msg="二次确认不匹配", data={"error": "confirm_mismatch"})
    updated = await auth_admin.update_user(user_id=user_id, password=password, request_id=request_id)
    audit_ok = await _write_audit_log(
        request,
        admin_user=admin_user,
        action="reset_password",
        resource="app_user",
        resource_id=user_id,
        details={"reason": (payload.reason or "").strip()},
    )

    # One-time return. Admin should copy out immediately.
    return create_response(
        data={"temporary_password": password, "auth_user": updated, "audit_ok": audit_ok},
        msg="password_reset",
    )
