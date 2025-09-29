"""v1 版本路由集合。"""
from fastapi import APIRouter

from .messages import router as messages_router

v1_router = APIRouter()
v1_router.include_router(messages_router)

__all__ = ["v1_router"]