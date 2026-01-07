"""Seed manifest + file download endpoints (for client sync)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.services.exercise_library_service import ExerciseLibraryService

router = APIRouter(prefix="/seed", tags=["seed"])


def _get_exercise_library_service(request: Request) -> ExerciseLibraryService:
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


@router.get("/manifest")
async def get_seed_manifest(
    request: Request,
    response: Response,
    channel: str = Query(default="stable", min_length=1, max_length=50),
) -> dict[str, Any]:
    """客户端可按版本拉取并缓存的 seed manifest（目前仅包含官方动作库）。"""

    service = _get_exercise_library_service(request)
    await service.ensure_seeded()
    meta = await service.get_meta()

    resource = {
        "name": "exercise_library",
        "version": meta.version,
        "checksum": meta.checksum,
        "etag": _quote_etag(meta.checksum),
        "download_url": meta.downloadUrl,
        "update_strategy": {
            "type": "delta_via_api",
            "meta_url": "/api/v1/exercise/library/meta",
            "full_url": "/api/v1/exercise/library/full",
            "updates_url": "/api/v1/exercise/library/updates",
            "poll_interval_seconds": 86400,
        },
    }

    body: dict[str, Any] = {
        "channel": channel,
        "updated_at": meta.lastUpdated,
        "resources": [resource],
    }

    manifest_etag = _quote_etag(f"seed_manifest:{channel}:{meta.checksum}")
    response.headers["ETag"] = manifest_etag
    response.headers["Cache-Control"] = "public, max-age=60"
    if _if_none_match_hit(request.headers.get("if-none-match"), manifest_etag):
        return Response(status_code=304, headers={"ETag": manifest_etag, "Cache-Control": "public, max-age=60"})

    return body


@router.get("/files/{name}")
async def download_seed_file(
    name: str,
    request: Request,
    response: Response,
    version: int | None = Query(default=None, ge=1),
):
    """下载 seed 文件（支持 If-None-Match / ETag）。"""

    if name not in {"exercise_library", "exercise_library_full"}:
        raise HTTPException(status_code=404, detail={"code": "seed_not_found", "message": f"Unknown seed: {name}"})

    service = _get_exercise_library_service(request)
    await service.ensure_seeded()
    meta = await service.get_meta(version=version)

    etag = _quote_etag(meta.checksum)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=3600"
    if _if_none_match_hit(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})

    items = await service.get_full(version=version)
    return [item.model_dump(mode="json") for item in items]
