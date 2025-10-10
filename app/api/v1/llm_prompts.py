"""LLM Prompt 管理路由。"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import AuthenticatedUser, get_current_user

from .llm_common import SyncDirection, SyncRequest, create_response, get_service


router = APIRouter(prefix="/llm", tags=["llm"])


class PromptBase(BaseModel):
    """Prompt 公共字段。"""

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
            except json.JSONDecodeError as exc:  # pragma: no cover - 输入校验
                raise ValueError("tools_json 必须是合法 JSON 字符串") from exc
        raise ValueError("tools_json 仅支持 dict/list 或 JSON 字符串")


class PromptCreate(PromptBase):
    """创建 Prompt 请求体。"""

    name: str
    content: str
    auto_sync: bool = False


class PromptUpdate(PromptBase):
    """更新 Prompt 请求体。"""

    auto_sync: bool = False


@router.get("/prompts")
async def list_prompts(
    request: Request,
    keyword: Optional[str] = Query(default=None),  # noqa: B008
    only_active: Optional[bool] = Query(default=None),  # noqa: B008
    page: int = Query(default=1, ge=1),  # noqa: B008
    page_size: int = Query(default=20, ge=1, le=100),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
                detail=create_response(code=502, msg=f"同步到 Supabase 失败: {exc}"),
            ) from exc
    return create_response(data=prompt, msg="更新成功")


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        prompt = await service.activate_prompt(prompt_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Prompt 不存在"),
        )
    return create_response(data=prompt, msg="启用成功")


@router.post("/prompts/sync")
async def sync_prompts(
    request: Request,
    body: SyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
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


__all__ = [
    "router",
    "PromptBase",
    "PromptCreate",
    "PromptUpdate",
]
