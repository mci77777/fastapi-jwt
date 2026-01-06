"""Mobile: /v1/me - user snapshot aggregation (SSOT: Supabase)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user
from app.core.exceptions import create_error_response
from app.repositories.user_repo import UserRepository
from app.services.supabase_admin import SupabaseAdminError

router = APIRouter(tags=["mobile"])


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: str
    user_type: Literal["anonymous", "permanent"]
    server_time: str = Field(..., description="Server time (ISO-8601, UTC)")
    profile: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    entitlements: Optional[dict[str, Any]] = None


_PROFILE_FIELDS = {
    "display_name",
    "avatar_url",
    "bio",
    "gender",
    "height_cm",
    "weight_kg",
    "fitness_level",
    "fitness_goals",
    "workout_days",
    "total_workout_count",
    "weekly_active_minutes",
    "likes_received",
    "is_anonymous",
    "last_updated",
}

_SETTINGS_FIELDS = {
    "theme_mode",
    "language_code",
    "measurement_system",
    "notifications_enabled",
    "sounds_enabled",
    "location_sharing_enabled",
    "data_sharing_enabled",
    "allow_workout_sharing",
    "auto_backup_enabled",
    "backup_frequency",
    "last_backup_time",
    "ai_memory_enabled",
    "last_updated",
}

_ENTITLEMENT_FIELDS = {
    "tier",
    "expires_at",
    "flags",
    "last_updated",
}


def _pick_fields(data: Optional[dict[str, Any]], allowed: set[str]) -> Optional[dict[str, Any]]:
    if not isinstance(data, dict):
        return None
    return {k: data.get(k) for k in allowed if k in data}


@router.get("/me", response_model=MeResponse)
async def get_me(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> MeResponse:
    server_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Anonymous user: minimal response (do not read Supabase user tables by default)
    if current_user.is_anonymous:
        return MeResponse(uid=current_user.uid, user_type="anonymous", server_time=server_time)

    repo = getattr(request.app.state, "user_repository", None)
    if not isinstance(repo, UserRepository):
        return create_error_response(
            status_code=503,
            code="user_repository_unavailable",
            message="User repository unavailable",
        )

    try:
        bundle = await repo.get_user_bundle(current_user.uid)
    except SupabaseAdminError as exc:
        return create_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
            hint=exc.hint,
        )
    except Exception:
        return create_error_response(
            status_code=500,
            code="user_data_fetch_failed",
            message="Failed to fetch user data",
        )

    return MeResponse(
        uid=current_user.uid,
        user_type="permanent",
        server_time=server_time,
        profile=_pick_fields(bundle.get("profile"), _PROFILE_FIELDS),
        settings=_pick_fields(bundle.get("settings"), _SETTINGS_FIELDS),
        entitlements=_pick_fields(bundle.get("entitlements"), _ENTITLEMENT_FIELDS),
    )

