"""Admin: manage user_entitlements (SSOT: Supabase)."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.base import get_current_user_from_token
from app.auth import AuthenticatedUser
from app.db import get_sqlite_manager
from app.services.supabase_admin import SupabaseAdminClient

from .llm_common import create_response, is_dashboard_admin_user

router = APIRouter(prefix="/admin", tags=["user-entitlements-admin"])


async def require_dashboard_admin(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
) -> AuthenticatedUser:
    if is_dashboard_admin_user(current_user):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=create_response(code=403, msg="Admin privileges required"),
    )


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


class UserEntitlementsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1, description="Supabase auth.users.id (UUID as string)")
    tier: str = Field(default="free", description="Subscription tier: free/pro/...")
    expires_at: int | None = Field(default=None, ge=0, description="Epoch milliseconds (nullable)")
    flags: dict[str, Any] = Field(default_factory=dict, description="Feature flags (jsonb)")
    last_updated: int | None = Field(default=None, ge=0, description="Epoch milliseconds")
    exists: bool = Field(default=True, description="Whether the row exists in Supabase")


@router.get("/user-entitlements", response_model=None)
async def get_user_entitlements(
    request: Request,
    user_id: str = Query(..., min_length=1, description="Target user_id (UUID as string)"),  # noqa: B008
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)
    row = await supabase.fetch_one_by_user_id(table="user_entitlements", user_id=user_id)
    if not isinstance(row, dict):
        return create_response(
            data=UserEntitlementsSnapshot(
                user_id=user_id,
                tier="free",
                expires_at=None,
                flags={},
                last_updated=None,
                exists=False,
            ).model_dump(mode="json"),
            msg="ok",
        )

    return create_response(
        data=UserEntitlementsSnapshot(
            user_id=str(row.get("user_id") or user_id),
            tier=str(row.get("tier") or "free"),
            expires_at=(int(row.get("expires_at")) if isinstance(row.get("expires_at"), int) else None),
            flags=(row.get("flags") if isinstance(row.get("flags"), dict) else {}),
            last_updated=(int(row.get("last_updated")) if isinstance(row.get("last_updated"), int) else None),
            exists=True,
        ).model_dump(mode="json"),
        msg="ok",
    )


class UserEntitlementsUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1)
    tier: str = Field(..., min_length=1)
    expires_at: int | None = Field(default=None, ge=0)
    flags: dict[str, Any] = Field(default_factory=dict)


@router.post("/user-entitlements", response_model=None)
async def upsert_user_entitlements(
    payload: UserEntitlementsUpsertRequest,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)

    now_ms = int(time.time() * 1000)
    values: dict[str, Any] = {
        "user_id": payload.user_id,
        "tier": payload.tier,
        "expires_at": payload.expires_at,
        "flags": payload.flags,
        "last_updated": now_ms,
    }

    row = await supabase.upsert_one(table="user_entitlements", values=values, on_conflict="user_id")

    if not isinstance(row, dict):
        return create_response(code=502, msg="Supabase upsert failed", data=None)

    return create_response(
        data=UserEntitlementsSnapshot(
            user_id=str(row.get("user_id") or payload.user_id),
            tier=str(row.get("tier") or payload.tier),
            expires_at=(int(row.get("expires_at")) if isinstance(row.get("expires_at"), int) else payload.expires_at),
            flags=(row.get("flags") if isinstance(row.get("flags"), dict) else payload.flags),
            last_updated=(int(row.get("last_updated")) if isinstance(row.get("last_updated"), int) else now_ms),
            exists=True,
        ).model_dump(mode="json"),
        msg="updated",
    )


class UserEntitlementsTierCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str = Field(..., min_length=1)
    count: int = Field(..., ge=0)


class UserEntitlementsStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_time_ms: int = Field(..., ge=0)
    total_rows: int = Field(..., ge=0)
    tiers: list[UserEntitlementsTierCount] = Field(default_factory=list)
    pro_active: int = Field(..., ge=0)
    pro_expired: int = Field(..., ge=0)


@router.get("/user-entitlements/stats", response_model=None)
async def get_user_entitlements_stats(
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)
    now_ms = int(time.time() * 1000)

    total_rows = await supabase.count_rows(table="user_entitlements")
    presets = await _list_effective_tier_presets(request)

    tier_counts: list[UserEntitlementsTierCount] = []
    known_sum = 0
    for preset in presets:
        tier = _normalize_tier(preset.get("tier"))
        if not tier or tier == "other":
            continue
        count = await supabase.count_rows(table="user_entitlements", filters={"tier": f"eq.{tier}"})
        tier_counts.append(UserEntitlementsTierCount(tier=tier, count=int(count)))
        known_sum += int(count)

    other_rows = max(int(total_rows) - int(known_sum), 0)
    tier_counts.append(UserEntitlementsTierCount(tier="other", count=int(other_rows)))

    pro_rows = next((item.count for item in tier_counts if item.tier == "pro"), 0)
    if pro_rows > 0:
        pro_active = await supabase.count_rows(
            table="user_entitlements",
            filters={
                "tier": "eq.pro",
                "or": f"(expires_at.is.null,expires_at.gt.{now_ms})",
            },
        )
        pro_expired = max(int(pro_rows) - int(pro_active), 0)
    else:
        pro_active = 0
        pro_expired = 0

    payload = UserEntitlementsStats(
        server_time_ms=now_ms,
        total_rows=int(total_rows),
        tiers=tier_counts,
        pro_active=int(pro_active),
        pro_expired=int(pro_expired),
    ).model_dump(mode="json")
    return create_response(data=payload, msg="ok")


class UserEntitlementsTierPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str = Field(..., min_length=1)
    default_expires_days: int | None = Field(default=None, ge=0, description="Default duration days (nullable)")
    flags: dict[str, Any] = Field(default_factory=dict)


class UserEntitlementsTierPresetUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str = Field(..., min_length=1)
    default_expires_days: int | None = Field(default=None, ge=0)
    flags: dict[str, Any] = Field(default_factory=dict)


@router.get("/user-entitlements/presets", response_model=None)
async def get_user_entitlements_tier_presets(
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    presets = await _list_effective_tier_presets(request)
    data = [UserEntitlementsTierPreset(**item).model_dump(mode="json") for item in presets]
    return create_response(data=data, msg="ok")


@router.post("/user-entitlements/presets", response_model=None)
async def upsert_user_entitlements_tier_preset(
    payload: UserEntitlementsTierPresetUpsertRequest,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    tier = _normalize_tier(payload.tier)
    if not tier:
        return create_response(code=400, msg="tier is required", data=None)
    if tier == "other":
        return create_response(code=400, msg="tier 'other' is reserved", data=None)

    db = get_sqlite_manager(request.app)
    flags_json = json.dumps(payload.flags or {}, ensure_ascii=False)
    await db.execute(
        """
        INSERT INTO user_entitlement_tier_presets(tier, default_expires_days, default_flags_json, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(tier) DO UPDATE SET
          default_expires_days = excluded.default_expires_days,
          default_flags_json = excluded.default_flags_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            tier,
            int(payload.default_expires_days) if payload.default_expires_days is not None else None,
            flags_json,
        ),
    )

    presets = await _list_effective_tier_presets(request)
    row = next((item for item in presets if _normalize_tier(item.get("tier")) == tier), None) or {
        "tier": tier,
        "default_expires_days": payload.default_expires_days,
        "flags": payload.flags,
    }
    return create_response(data=UserEntitlementsTierPreset(**row).model_dump(mode="json"), msg="updated")


@router.delete("/user-entitlements/presets/{tier}", response_model=None)
async def delete_user_entitlements_tier_preset(
    tier: str,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    normalized = _normalize_tier(tier)
    if not normalized:
        return create_response(code=400, msg="tier is required", data=None)
    if normalized == "other":
        return create_response(code=400, msg="tier 'other' is reserved", data=None)

    db = get_sqlite_manager(request.app)
    await db.execute("DELETE FROM user_entitlement_tier_presets WHERE tier = ?", (normalized,))
    return create_response(data={"tier": normalized}, msg="deleted")


@router.get("/user-entitlements/list", response_model=None)
async def list_user_entitlements(
    request: Request,
    page: int = Query(1, ge=1, le=100000, description="1-based page number"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    tier: str | None = Query(None, description="Filter by tier (e.g. free/pro)"),  # noqa: B008
    active_only: bool = Query(False, description="Only active (expires_at is null or in the future)"),  # noqa: B008
    user_id: str | None = Query(None, description="Filter by user_id (UUID string)"),  # noqa: B008
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
) -> dict[str, Any]:
    supabase = _get_supabase_admin(request)
    now_ms = int(time.time() * 1000)

    filters: dict[str, Any] = {}
    if user_id:
        filters["user_id"] = f"eq.{str(user_id).strip()}"
    if tier:
        filters["tier"] = f"eq.{str(tier).strip().lower()}"
    if active_only:
        filters["or"] = f"(expires_at.is.null,expires_at.gt.{now_ms})"

    limit = int(page_size)
    offset = (int(page) - 1) * limit
    items, total = await supabase.fetch_list(
        table="user_entitlements",
        filters=filters or None,
        select="user_id,tier,expires_at,flags,last_updated",
        order="last_updated.desc",
        limit=limit,
        offset=offset,
        with_count=True,
    )

    payload = {
        "items": items,
        "total": int(total if total is not None else len(items)),
        "page": int(page),
        "page_size": int(page_size),
    }
    return create_response(data=payload, msg="ok")
