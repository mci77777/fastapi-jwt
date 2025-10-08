"""v1 版本路由集合。"""
from fastapi import APIRouter

from .base import router as base_router
from .health import router as health_router
from .llm import router as llm_router
from .messages import router as messages_router
from .metrics import router as metrics_router

v1_router = APIRouter()
v1_router.include_router(base_router)
v1_router.include_router(health_router)
v1_router.include_router(llm_router)
v1_router.include_router(messages_router)
v1_router.include_router(metrics_router)

__all__ = ["v1_router"]
