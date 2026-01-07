"""Admin: manage user_entitlements (SSOT: Supabase)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.base import get_current_user_from_token
from app.auth import AuthenticatedUser
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
            detail=create_response(code=503, msg="Supabase admin client unavailable"),
        )
    return client


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
