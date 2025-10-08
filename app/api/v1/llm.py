"""LLM 配置与 Prompt 管理接口。"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import AuthenticatedUser, get_current_user
from app.services.ai_config_service import AIConfigService
from app.services.monitor_service import EndpointMonitor

router = APIRouter(prefix="/llm", tags=["llm"])


def create_response(
    data: Any = None,
    *,
    code: int = 200,
    msg: str = "success",
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "msg": msg, "data": data}
    payload.update(extra)
    return payload


def get_service(request: Request) -> AIConfigService:
    service = getattr(request.app.state, "ai_config_service", None)
    if not isinstance(service, AIConfigService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI 配置服务未就绪"),
        )
    return service


def get_monitor(request: Request) -> EndpointMonitor:
    monitor = getattr(request.app.state, "endpoint_monitor", None)
    if not isinstance(monitor, EndpointMonitor):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI monitor not initialized"),
        )
    return monitor


class SyncDirection(str, Enum):
    """Supabase 同步方向。"""

    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


class SyncRequest(BaseModel):
    """同步请求体。"""

    direction: SyncDirection = Field(default=SyncDirection.PUSH)


class APIEndpointBase(BaseModel):
    """AI 端点配置基础字段。"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=512)
    timeout: Optional[int] = Field(default=60, ge=1, le=600)
    is_active: Optional[bool] = True
    is_default: Optional[bool] = False


class AIModelCreate(APIEndpointBase):
    """创建端点请求。"""

    name: str
    base_url: str
    auto_sync: bool = False


class AIModelUpdate(APIEndpointBase):
    """更新端点请求。"""

    id: int
    auto_sync: bool = False


class PromptBase(BaseModel):
    """Prompt 基础字段。"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=120)
    content: Optional[str] = Field(None, min_length=1)
    version: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    tools_json: Optional[Any] = None
    is_active: Optional[bool] = False

    @field_validator("tools_json")
    @classmethod
    def parse_tools_json(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("tools_json 必须是合法 JSON 字符串") from exc
        raise ValueError("tools_json 仅支持对象、数组或 JSON 字符串")


class PromptCreate(PromptBase):
    """创建 Prompt 请求。"""

    name: str
    content: str
    auto_sync: bool = False


class PromptUpdate(PromptBase):
    auto_sync: bool = False


class MonitorControlRequest(BaseModel):
    """Control payload for the endpoint monitor."""

    interval_seconds: int = Field(..., ge=10, le=600, description="Interval seconds")


class PromptTestRequest(BaseModel):
    """Prompt 测试请求。"""

    prompt_id: int = Field(..., description="Prompt ID")
    endpoint_id: int = Field(..., description="端点 ID")
    message: str = Field(..., min_length=1, description="测试消息内容")
    model: Optional[str] = Field(None, description="指定模型，可选")


# --------------------------------------------------------------------------- #
# AI 端点管理
# --------------------------------------------------------------------------- #


@router.get("/models")
async def list_ai_models(
    request: Request,
    keyword: Optional[str] = Query(default=None, description="搜索关键字"),
    only_active: Optional[bool] = Query(default=None, description="仅启用"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
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
            detail=create_response(code=404, msg="端点不存在"),
        )
    if payload.auto_sync:
        try:
            endpoint = await service.push_endpoint_to_supabase(payload.id)
        except Exception as exc:  # pragma: no cover - 外部请求失败
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(code=502, msg=f"同步到 Supabase 失败: {exc}"),
            ) from exc
    return create_response(data=endpoint, msg="更新成功")


@router.delete("/models/{endpoint_id}")
async def delete_ai_model(
    endpoint_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        await service.delete_endpoint(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="端点不存在"),
        )
    return create_response(msg="删除成功")


@router.post("/models/{endpoint_id}/check")
async def check_ai_endpoint(
    endpoint_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        endpoint = await service.refresh_endpoint_status(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="端点不存在"),
        )
    return create_response(data=endpoint, msg="检测完成")


@router.post("/models/check-all")
async def check_all_endpoints(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    results = await service.refresh_all_status()
    return create_response(data=results, msg="批量检测完成")


@router.post("/models/{endpoint_id}/sync")
async def sync_single_endpoint(
    endpoint_id: int,
    request: Request,
    body: SyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    direction = body.direction if body else SyncDirection.PUSH
    try:
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            endpoint = await service.push_endpoint_to_supabase(endpoint_id)
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            await service.pull_endpoints_from_supabase()
            endpoint = await service.get_endpoint(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="端点不存在"),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    direction = body.direction if body else SyncDirection.PUSH
    try:
        results: list[dict[str, Any]] = []
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            results = await service.push_all_to_supabase()
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            results = await service.pull_endpoints_from_supabase()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=results, msg=f"批量同步完成({direction.value})")


@router.get("/status/supabase")
async def supabase_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    status_payload = await service.supabase_status()
    return create_response(data=status_payload)


# --------------------------------------------------------------------------- #
# Prompt 管理
# --------------------------------------------------------------------------- #


@router.get("/monitor/status")
async def monitor_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    monitor = get_monitor(request)
    return create_response(data=monitor.snapshot())


@router.post("/monitor/start")
async def start_monitor(
    payload: MonitorControlRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    monitor = get_monitor(request)
    await monitor.stop()
    return create_response(data=monitor.snapshot(), msg="Monitor stopped")


@router.get("/prompts")
async def list_prompts(
    request: Request,
    keyword: Optional[str] = Query(default=None),
    only_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    items, total = await service.list_prompts(
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


@router.get("/prompts/{prompt_id}")
async def get_prompt_detail(
    prompt_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        prompt = await service.get_prompt(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Prompt 不存在"),
        )
    return create_response(data=prompt)


@router.post("/prompts")
async def create_prompt(
    payload: PromptCreate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    prompt = await service.create_prompt(
        payload.model_dump(exclude={"auto_sync"}, exclude_none=True),
        auto_sync=payload.auto_sync,
    )
    return create_response(data=prompt, msg="创建成功")


@router.put("/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        prompt = await service.update_prompt(
            prompt_id,
            payload.model_dump(exclude={"auto_sync"}, exclude_none=True),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Prompt 不存在"),
        )
    if payload.auto_sync:
        try:
            prompt = await service.push_prompt_to_supabase(prompt_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(code=502, msg=f"同步 Supabase 失败: {exc}"),
            ) from exc
    return create_response(data=prompt, msg="更新成功")


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        await service.delete_prompt(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Prompt 不存在"),
        )
    return create_response(msg="删除成功")


@router.post("/prompts/{prompt_id}/activate")
async def activate_prompt(
    prompt_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        prompt = await service.activate_prompt(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Prompt 不存在"),
        )
    return create_response(data=prompt, msg="激活成功")


@router.post("/prompts/sync")
async def sync_prompts(
    request: Request,
    body: SyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    direction = body.direction if body else SyncDirection.PUSH
    try:
        results: list[dict[str, Any]] = []
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            results = await service.push_all_prompts_to_supabase()
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            results = await service.pull_prompts_from_supabase()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=results, msg=f"Prompt 同步完成({direction.value})")


@router.get("/prompts/{prompt_id}/tests")
async def prompt_tests(
    prompt_id: int,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    tests = await service.list_prompt_tests(prompt_id, limit=limit)
    return create_response(data=tests)


@router.post("/prompts/test")
async def test_prompt(
    payload: PromptTestRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = get_service(request)
    try:
        result = await service.test_prompt(
            prompt_id=payload.prompt_id,
            endpoint_id=payload.endpoint_id,
            message=payload.message,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg=str(exc)),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=create_response(code=502, msg=str(exc)),
        ) from exc
    return create_response(data=result, msg="测试完成")
