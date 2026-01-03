"""v1 版本路由集合。"""

import logging

from fastapi import APIRouter

from .agents import router as agents_router
from .base import router as base_router
from .dashboard import router as dashboard_router
from .health import router as health_router
from .llm import router as llm_router
from .messages import router as messages_router
from .metrics import router as metrics_router
from .exercise_library import router as exercise_library_router
from .admin_exercise_library import router as admin_exercise_library_router

logger = logging.getLogger(__name__)

v1_router = APIRouter()
v1_router.include_router(base_router)
v1_router.include_router(dashboard_router)
logger.info("[ROUTER_INIT] Dashboard router registered with %d routes", len(dashboard_router.routes))
v1_router.include_router(health_router)
v1_router.include_router(llm_router)
v1_router.include_router(messages_router)
v1_router.include_router(metrics_router)
v1_router.include_router(agents_router)
v1_router.include_router(exercise_library_router)
v1_router.include_router(admin_exercise_library_router)
logger.info("[ROUTER_INIT] Agents router registered with %d routes", len(agents_router.routes))

__all__ = ["v1_router"]
