"""LLM 测试相关路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, conint

from app.auth import AuthenticatedUser, get_current_user

from .llm_common import create_response, get_jwt_test_service, get_service


router = APIRouter(prefix="/llm", tags=["llm"])


class PromptTestRequest(BaseModel):
    """Prompt 测试请求体。"""

    prompt_id: int = Field(..., description="Prompt ID")
    endpoint_id: int = Field(..., description="接口 ID")
    message: str = Field(..., min_length=1, description="测试消息内容")
    model: str | None = Field(None, description="可选模型名称")


class JwtDialogRequest(BaseModel):
    """JWT 对话模拟请求。"""

    prompt_id: int
    endpoint_id: int
    message: str
    model: str | None = None
    username: str | None = None


class JwtLoadTestRequest(BaseModel):
    """JWT 并发压测请求。"""

    prompt_id: int
    endpoint_id: int
    message: str
    batch_size: conint(ge=1, le=1000) = 1  # type: ignore[valid-type]
    concurrency: conint(ge=1, le=1000) = 1  # type: ignore[valid-type]
    model: str | None = None
    username: str | None = None
    stop_on_error: bool = False


@router.get("/prompts/{prompt_id}/tests")
async def prompt_tests(
    prompt_id: int,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    tests = await service.list_prompt_tests(prompt_id, limit=limit)
    return create_response(data=tests)


@router.post("/prompts/test")
async def test_prompt(
    payload: PromptTestRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
    return create_response(data=result, msg="测试成功")


@router.post("/tests/dialog")
async def simulate_jwt_dialog(
    payload: JwtDialogRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    result = await service.simulate_dialog(payload.model_dump())
    return create_response(data=result)


@router.post("/tests/load")
async def run_jwt_load_test(
    payload: JwtLoadTestRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    result = await service.run_load_test(payload.model_dump())
    return create_response(data=result, msg="压测完成")


@router.get("/tests/runs/{run_id}")
async def get_jwt_run(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    result = await service.get_run(run_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Run 不存在"),
        )
    return create_response(data=result)


__all__ = [
    "router",
    "PromptTestRequest",
    "JwtDialogRequest",
    "JwtLoadTestRequest",
]
