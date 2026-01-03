"""Admin: Exercise Library seed publish endpoints (versioned snapshots)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.api.v1.base import get_current_user_from_token
from app.auth import AuthenticatedUser
from app.services.exercise_library_service import ExerciseDto, ExerciseLibraryError, ExerciseLibraryService
from .llm_common import is_dashboard_admin_user

router = APIRouter(prefix="/admin/exercise/library", tags=["exercise-library-admin"])

_exercise_list_adapter: TypeAdapter[list[ExerciseDto]] = TypeAdapter(list[ExerciseDto])


def _get_service(request: Request) -> ExerciseLibraryService:
    sqlite_manager = request.app.state.sqlite_manager
    return ExerciseLibraryService(sqlite_manager, seed_path=Path("assets") / "exercise" / "exercise_official_seed.json")


async def require_dashboard_admin(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
) -> AuthenticatedUser:
    if is_dashboard_admin_user(current_user):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "admin_required", "message": "Admin privileges required"},
    )


@router.post("/publish")
async def publish_exercise_library_seed(
    request: Request,
    body: Any = Body(...),
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
):
    """发布/更新官方动作库种子（写入 sqlite.exercise_library_snapshots）。"""

    items: list[ExerciseDto]
    version_override: int | None = None
    generated_at_ms: int | None = None
    if isinstance(body, list):
        items = _exercise_list_adapter.validate_python(body)
    elif isinstance(body, dict):
        candidate = body.get("items") or body.get("payload") or body.get("exercises")
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_body",
                    "message": "Expected JSON array or object with items/payload/exercises",
                },
            )
        # 推荐：直接上传 assets/exercise/exercise_official_seed.json（ExerciseSeedData）
        if "payload" in body:
            try:
                version_override = int(body.get("entityVersion")) if body.get("entityVersion") is not None else None
            except Exception:
                version_override = None
            try:
                generated_at_ms = int(body.get("generatedAt")) if body.get("generatedAt") is not None else None
            except Exception:
                generated_at_ms = None
        items = _exercise_list_adapter.validate_python(candidate)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_body", "message": "Expected JSON array or object body"},
        )

    service = _get_service(request)
    try:
        meta = await service.publish(items, generated_at_ms=generated_at_ms, version_override=version_override)
        return meta.model_dump(mode="json")
    except ExerciseLibraryError as exc:
        status_code = 400 if exc.code in {"empty_seed"} or exc.code.startswith("invalid_") else 503
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc)}) from exc


class ExerciseLibraryPatchUpdate(BaseModel):
    """字段级更新：必须包含 id，其余字段按需提供。"""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, max_length=200)


class ExerciseLibraryPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseVersion: int = Field(..., ge=1, description="当前快照版本（并发保护）")
    added: list[dict[str, Any]] = Field(default_factory=list)
    updated: list[ExerciseLibraryPatchUpdate] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)
    generatedAt: int | None = Field(default=None, ge=0)


@router.post("/patch")
async def patch_exercise_library_seed(
    payload: ExerciseLibraryPatchRequest,
    request: Request,
    _: AuthenticatedUser = Depends(require_dashboard_admin),  # noqa: B008
):
    """增量更新官方动作库（added/updated/deleted）并发布新版本。"""

    service = _get_service(request)
    try:
        meta = await service.apply_patch_and_publish(
            base_version=int(payload.baseVersion),
            added=list(payload.added or []),
            updated=[item.model_dump(mode="python") for item in (payload.updated or [])],
            deleted=list(payload.deleted or []),
            generated_at_ms=(int(payload.generatedAt) if payload.generatedAt is not None else None),
        )
        return meta.model_dump(mode="json")
    except ExerciseLibraryError as exc:
        if exc.code == "version_conflict":
            status_code = status.HTTP_409_CONFLICT
        elif exc.code == "patch_target_not_found":
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST if exc.code.startswith("invalid_") else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc)}) from exc
