"""Exercise Library (official seed) sync endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.services.exercise_library_service import ExerciseLibraryError, ExerciseLibraryService

router = APIRouter(prefix="/exercise/library", tags=["exercise-library"])


def _get_service(request: Request) -> ExerciseLibraryService:
    sqlite_manager = request.app.state.sqlite_manager
    return ExerciseLibraryService(sqlite_manager, seed_path=Path("assets") / "exercise" / "exercise_official_seed.json")


def _quote_etag(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return "\"\""
    if v.startswith(("W/\"", "\"")) and v.endswith("\""):
        return v
    return f"\"{v}\""


def _if_none_match_hit(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False
    candidates = [v.strip() for v in header_value.split(",") if v.strip()]
    return etag in candidates or etag.strip() in candidates


@router.get("/meta")
async def get_exercise_library_meta(
    request: Request,
    response: Response,
    version: int | None = Query(default=None, ge=1),
):
    service = _get_service(request)
    await service.ensure_seeded()
    meta = await service.get_meta(version=version)
    etag = _quote_etag(meta.checksum)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    if _if_none_match_hit(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=60"})
    return meta.model_dump(mode="json")


@router.get("/full")
async def get_exercise_library_full(
    request: Request,
    response: Response,
    version: int | None = Query(default=None, ge=1),
):
    service = _get_service(request)
    await service.ensure_seeded()
    meta = await service.get_meta(version=version)
    etag = _quote_etag(meta.checksum)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=3600"
    if _if_none_match_hit(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})

    items = await service.get_full(version=version)
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
