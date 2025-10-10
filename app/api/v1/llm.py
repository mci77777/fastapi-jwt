"""LLM 相关路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from .llm_mappings import router as mappings_router
from .llm_models import router as models_router
from .llm_prompts import router as prompts_router
from .llm_tests import router as tests_router

router = APIRouter()
router.include_router(models_router)
router.include_router(mappings_router)
router.include_router(prompts_router)
router.include_router(tests_router)

__all__ = ["router"]
