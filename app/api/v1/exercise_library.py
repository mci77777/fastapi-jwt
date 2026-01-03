"""Exercise Library (official seed) sync endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.exercise_library_service import ExerciseLibraryError, ExerciseLibraryService

router = APIRouter(prefix="/exercise/library", tags=["exercise-library"])


def _get_service(request: Request) -> ExerciseLibraryService:
    sqlite_manager = request.app.state.sqlite_manager
    return ExerciseLibraryService(sqlite_manager, seed_path=Path("assets") / "exercise" / "exercise_official_seed.json")


@router.get("/meta")
async def get_exercise_library_meta(request: Request):
    service = _get_service(request)
    await service.ensure_seeded()
    meta = await service.get_meta()
    return meta.model_dump(mode="json")


@router.get("/full")
async def get_exercise_library_full(request: Request):
    service = _get_service(request)
    await service.ensure_seeded()
    items = await service.get_full()
    return [item.model_dump(mode="json") for item in items]


@router.get("/updates")
async def get_exercise_library_updates(
    request: Request,
    from_version: int = Query(..., alias="from"),
    to_version: int = Query(..., alias="to"),
):
    service = _get_service(request)
    await service.ensure_seeded()
    try:
        updates = await service.get_updates(from_version=from_version, to_version=to_version)
        return updates.model_dump(mode="json")
    except ExerciseLibraryError as exc:
        status = 400 if exc.code.startswith("invalid_") else 404 if exc.code == "snapshot_not_found" else 503
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
