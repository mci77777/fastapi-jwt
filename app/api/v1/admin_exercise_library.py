"""Admin: Exercise Library seed publish endpoints (versioned snapshots)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import TypeAdapter

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
