"""LLM 模型相关路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user

from .llm_common import SyncDirection, SyncRequest, create_response, get_monitor, get_service


router = APIRouter(prefix="/llm", tags=["llm"])


class APIEndpointBase(BaseModel):
    """AI 接口公共字段。"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=512)
    timeout: Optional[int] = Field(default=60, ge=1, le=600)
    is_active: Optional[bool] = True
    is_default: Optional[bool] = False
    model_list: Optional[list[str]] = None


class AIModelCreate(APIEndpointBase):
    """创建接口请求体。"""

    name: str
    base_url: str
    auto_sync: bool = False


class AIModelUpdate(APIEndpointBase):
    """更新接口请求体。"""

    id: int
    auto_sync: bool = False


class MonitorControlRequest(BaseModel):
    """Endpoint 监控控制参数。"""

    interval_seconds: int = Field(..., ge=10, le=600, description="Interval seconds")


@router.get("/models")
async def list_ai_models(
    request: Request,
    keyword: Optional[str] = Query(default=None, description="关键词"),  # noqa: B008
    only_active: Optional[bool] = Query(default=None, description="是否仅活跃"),  # noqa: B008
    page: int = Query(default=1, ge=1),  # noqa: B008
    page_size: int = Query(default=20, ge=1, le=100),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    items, total = await service.list_endpoints(
        keyword=keyword,
        only_active=only_active,
        page=page,
        page_size=page_size,
    )
    return create_response(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/models")
async def create_ai_model(
    payload: AIModelCreate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    endpoint = await service.create_endpoint(
        payload.model_dump(exclude={"auto_sync"}, exclude_none=True),
        auto_sync=payload.auto_sync,
    )
    return create_response(data=endpoint, msg="创建成功")


@router.put("/models")
async def update_ai_model(
    payload: AIModelUpdate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        endpoint = await service.update_endpoint(
            payload.id,
            payload.model_dump(
                exclude={"id", "auto_sync"},
                exclude_none=True,
            ),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="接口不存在"),
        )
    if payload.auto_sync:
        try:
            endpoint = await service.push_endpoint_to_supabase(payload.id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(code=502, msg=f"同步到 Supabase 失败: {exc}"),
            ) from exc
    return create_response(data=endpoint, msg="更新成功")


@router.delete("/models/{endpoint_id}")
async def delete_ai_model(
    endpoint_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        await service.delete_endpoint(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="接口不存在"),
        )
    return create_response(msg="删除成功")


@router.post("/models/{endpoint_id}/check")
async def check_ai_endpoint(
    endpoint_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        endpoint = await service.refresh_endpoint_status(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="接口不存在"),
        )
    return create_response(data=endpoint, msg="检测完成")


@router.post("/models/check-all")
async def check_all_endpoints(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    results = await service.refresh_all_status()
    return create_response(data=results, msg="批量检测完成")


@router.post("/models/{endpoint_id}/sync")
async def sync_single_endpoint(
    endpoint_id: int,
    request: Request,
    body: SyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    payload = body or SyncRequest()
    direction = payload.direction
    try:
        endpoint: dict[str, Any] | None = None
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            endpoint = await service.push_endpoint_to_supabase(
                endpoint_id,
                overwrite=payload.overwrite,
                delete_missing=payload.delete_missing,
            )
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            await service.pull_endpoints_from_supabase(
                overwrite=payload.overwrite,
                delete_missing=payload.delete_missing,
            )
            try:
                endpoint = await service.get_endpoint(endpoint_id)
            except ValueError:
                endpoint = None
        if endpoint is None:
            endpoint = await service.get_endpoint(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="接口不存在"),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=endpoint, msg=f"同步完成({direction.value})")


@router.post("/models/sync")
async def sync_all_endpoints(
    request: Request,
    body: SyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    payload = body or SyncRequest()
    direction = payload.direction
    try:
        results: list[dict[str, Any]] = []
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            results = await service.push_all_to_supabase(
                overwrite=payload.overwrite,
                delete_missing=payload.delete_missing,
            )
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            results = await service.pull_endpoints_from_supabase(
                overwrite=payload.overwrite,
                delete_missing=payload.delete_missing,
            )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=results, msg=f"批量同步完成({direction.value})")


@router.get("/status/supabase")
async def supabase_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    status_payload = await service.supabase_status()
    return create_response(data=status_payload)


@router.get("/monitor/status")
async def monitor_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    monitor = get_monitor(request)
    return create_response(data=monitor.snapshot())


@router.post("/monitor/start")
async def start_monitor(
    payload: MonitorControlRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    monitor = get_monitor(request)
    try:
        await monitor.start(payload.interval_seconds)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_response(code=400, msg="Interval must be between 10 and 600 seconds"),
        ) from exc
    return create_response(data=monitor.snapshot(), msg="Monitor started")


@router.post("/monitor/stop")
async def stop_monitor(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    monitor = get_monitor(request)
    await monitor.stop()
    return create_response(data=monitor.snapshot(), msg="Monitor stopped")


__all__ = [
    "router",
    "APIEndpointBase",
    "AIModelCreate",
    "AIModelUpdate",
    "MonitorControlRequest",
]
