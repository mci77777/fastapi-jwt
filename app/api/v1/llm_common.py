"""LLM 路由通用依赖与工具函数。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.ai_config_service import AIConfigService
from app.services.jwt_test_service import JWTTestService
from app.services.model_mapping_service import ModelMappingService
from app.services.monitor_service import EndpointMonitor


def create_response(
    data: Any = None,
    *,
    code: int = 200,
    msg: str = "success",
    **extra: Any,
) -> dict[str, Any]:
    """构造统一响应格式。"""

    payload: dict[str, Any] = {"code": code, "msg": msg, "data": data}
    payload.update(extra)
    return payload


def get_service(request: Request) -> AIConfigService:
    """从 FastAPI app.state 中获取 AIConfigService。"""

    service = getattr(request.app.state, "ai_config_service", None)
    if not isinstance(service, AIConfigService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI 配置服务未初始化"),
        )
    return service


def get_monitor(request: Request) -> EndpointMonitor:
    """从 FastAPI app.state 中获取 EndpointMonitor。"""

    monitor = getattr(request.app.state, "endpoint_monitor", None)
    if not isinstance(monitor, EndpointMonitor):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI monitor not initialized"),
        )
    return monitor


def get_mapping_service(request: Request) -> ModelMappingService:
    """从 FastAPI app.state 中获取 ModelMappingService。"""

    service = getattr(request.app.state, "model_mapping_service", None)
    if not isinstance(service, ModelMappingService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="Model mapping service unavailable"),
        )
    return service


def get_jwt_test_service(request: Request) -> JWTTestService:
    """获取 JWTTestService。"""

    service = getattr(request.app.state, "jwt_test_service", None)
    if not isinstance(service, JWTTestService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="JWT test service unavailable"),
        )
    return service


class SyncDirection(str, Enum):
    """Supabase 同步方向。"""

    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


class SyncRequest(BaseModel):
    """同步请求体。"""

    direction: SyncDirection = Field(default=SyncDirection.PUSH)
    overwrite: bool = Field(default=False, description="是否覆盖本地/远端数据")
    delete_missing: bool = Field(default=False, description="是否删除缺失项，保持两端完全一致")


__all__ = [
    "create_response",
    "get_service",
    "get_monitor",
    "get_mapping_service",
    "get_jwt_test_service",
    "SyncDirection",
    "SyncRequest",
]
