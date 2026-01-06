"""Mobile API router (no /api prefix)."""

from fastapi import APIRouter

from app.api.v1.me import router as me_router

mobile_router = APIRouter()
mobile_router.include_router(me_router, prefix="/v1")

__all__ = ["mobile_router"]

