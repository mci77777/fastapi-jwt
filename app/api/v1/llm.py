"""LLM 配置管理端点（模型与 Prompt）。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.settings.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])


def create_response(data: Any = None, code: int = 200, msg: str = "success") -> Dict[str, Any]:
    """创建统一的响应格式。"""
    return {"code": code, "data": data, "msg": msg}


def get_supabase_headers() -> Dict[str, str]:
    """获取 Supabase REST API 请求头。"""
    settings = get_settings()
    service_key = settings.supabase_service_role_key
    if not service_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="Supabase 配置缺失"),
        )
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_supabase_base_url() -> str:
    """获取 Supabase REST API 基础 URL。"""
    settings = get_settings()
    project_id = settings.supabase_project_id
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="Supabase 配置缺失"),
        )
    return f"https://{project_id}.supabase.co/rest/v1"


def mask_api_key(api_key: Optional[str]) -> str:
    """遮挡 API Key，只显示前后各4个字符。"""
    if not api_key or len(api_key) < 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


# ==================== AI Models ====================


class AIModelCreate(BaseModel):
    """创建 AI 模型请求。"""

    name: str = Field(..., description="模型别名")
    model: str = Field(..., description="上游模型标识")
    base_url: Optional[str] = Field(None, description="基础地址")
    api_key: Optional[str] = Field(None, description="API 密钥")
    description: Optional[str] = Field(None, description="描述")
    timeout: int = Field(60, description="超时时间（秒）")
    is_active: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否默认")


class AIModelUpdate(BaseModel):
    """更新 AI 模型请求。"""

    id: int = Field(..., description="模型 ID")
    name: Optional[str] = Field(None, description="模型别名")
    model: Optional[str] = Field(None, description="上游模型标识")
    base_url: Optional[str] = Field(None, description="基础地址")
    api_key: Optional[str] = Field(None, description="API 密钥")
    description: Optional[str] = Field(None, description="描述")
    timeout: Optional[int] = Field(None, description="超时时间（秒）")
    is_active: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, description="是否默认")


@router.get("/models")
async def get_ai_models(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    only_active: Optional[bool] = Query(None, description="仅显示启用的"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 AI 模型列表。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        # 构建查询参数
        params = {
            "select": "*",
            "order": "created_at.desc",
            "offset": (page - 1) * page_size,
            "limit": page_size,
        }

        # 添加过滤条件
        filters = []
        if keyword:
            filters.append(f"or=(name.ilike.*{keyword}*,model.ilike.*{keyword}*)")
        if only_active is not None:
            filters.append(f"is_active=eq.{str(only_active).lower()}")

        if filters:
            params["and"] = f"({','.join(filters)})"

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取总数
            count_headers = {**headers, "Prefer": "count=exact"}
            count_response = await client.head(
                f"{base_url}/ai_model",
                headers=count_headers,
                params=params,
            )
            total = int(count_response.headers.get("Content-Range", "0-0/0").split("/")[-1])

            # 获取数据
            response = await client.get(
                f"{base_url}/ai_model",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

        items = response.json()

        # 遮挡 API Key
        for item in items:
            if item.get("api_key"):
                item["api_key_masked"] = mask_api_key(item["api_key"])
                del item["api_key"]
            else:
                item["api_key_masked"] = ""

        return create_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    except httpx.HTTPError as e:
        logger.error(f"获取 AI 模型列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="获取模型列表失败"),
        )


@router.post("/models")
async def create_ai_model(
    payload: AIModelCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """创建 AI 模型。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        # 如果设置为默认，先取消其他默认模型
        if payload.is_default:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{base_url}/ai_model?is_default=eq.true",
                    headers=headers,
                    json={"is_default": False},
                )

        # 创建新模型
        model_data = payload.model_dump(exclude_none=True)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/ai_model",
                headers=headers,
                json=model_data,
            )
            response.raise_for_status()

        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        # 遮挡 API Key
        if result.get("api_key"):
            result["api_key_masked"] = mask_api_key(result["api_key"])
            del result["api_key"]

        return create_response(data=result, msg="创建成功")

    except httpx.HTTPError as e:
        logger.error(f"创建 AI 模型失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="创建模型失败"),
        )


@router.put("/models")
async def update_ai_model(
    payload: AIModelUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新 AI 模型。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        model_id = payload.id
        update_data = payload.model_dump(exclude={"id"}, exclude_none=True)

        # 如果 api_key 为空字符串，不更新
        if "api_key" in update_data and not update_data["api_key"]:
            del update_data["api_key"]

        # 如果设置为默认，先取消其他默认模型
        if update_data.get("is_default"):
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{base_url}/ai_model?is_default=eq.true&id=neq.{model_id}",
                    headers=headers,
                    json={"is_default": False},
                )

        # 更新模型
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{base_url}/ai_model?id=eq.{model_id}",
                headers=headers,
                json=update_data,
            )
            response.raise_for_status()

        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        # 遮挡 API Key
        if result.get("api_key"):
            result["api_key_masked"] = mask_api_key(result["api_key"])
            del result["api_key"]

        return create_response(data=result, msg="更新成功")

    except httpx.HTTPError as e:
        logger.error(f"更新 AI 模型失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="更新模型失败"),
        )


# ==================== AI Prompts ====================


class AIPromptCreate(BaseModel):
    """创建 AI Prompt 请求。"""

    name: str = Field(..., description="Prompt 名称")
    version: str = Field(..., description="版本号")
    system_prompt: str = Field(..., description="系统 Prompt")
    tools_json: Optional[str] = Field(None, description="工具 JSON 字符串")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(False, description="是否激活")


class AIPromptUpdate(BaseModel):
    """更新 AI Prompt 请求。"""

    name: Optional[str] = Field(None, description="Prompt 名称")
    version: Optional[str] = Field(None, description="版本号")
    system_prompt: Optional[str] = Field(None, description="系统 Prompt")
    tools_json: Optional[str] = Field(None, description="工具 JSON 字符串")
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否激活")


@router.get("/prompts")
async def get_ai_prompts(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    only_active: Optional[bool] = Query(None, description="仅显示激活的"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 AI Prompt 列表。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        # 构建查询参数
        params = {
            "select": "*",
            "order": "created_at.desc",
            "offset": (page - 1) * page_size,
            "limit": page_size,
        }

        # 添加过滤条件
        filters = []
        if keyword:
            filters.append(f"or=(name.ilike.*{keyword}*,description.ilike.*{keyword}*)")
        if only_active is not None:
            filters.append(f"is_active=eq.{str(only_active).lower()}")

        if filters:
            params["and"] = f"({','.join(filters)})"

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取总数
            count_headers = {**headers, "Prefer": "count=exact"}
            count_response = await client.head(
                f"{base_url}/ai_prompt",
                headers=count_headers,
                params=params,
            )
            total = int(count_response.headers.get("Content-Range", "0-0/0").split("/")[-1])

            # 获取数据
            response = await client.get(
                f"{base_url}/ai_prompt",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

        items = response.json()

        # 解析 tools_json
        for item in items:
            if item.get("tools_json"):
                try:
                    item["tools_json"] = json.loads(item["tools_json"])
                except (json.JSONDecodeError, TypeError):
                    item["tools_json"] = None

        return create_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    except httpx.HTTPError as e:
        logger.error(f"获取 AI Prompt 列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="获取 Prompt 列表失败"),
        )


@router.get("/prompts/{prompt_id}")
async def get_ai_prompt_detail(
    prompt_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 AI Prompt 详情。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/ai_prompt?id=eq.{prompt_id}",
                headers=headers,
            )
            response.raise_for_status()

        items = response.json()
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_response(code=404, msg="Prompt 不存在"),
            )

        item = items[0]

        # 解析 tools_json
        if item.get("tools_json"):
            try:
                item["tools_json"] = json.loads(item["tools_json"])
            except (json.JSONDecodeError, TypeError):
                item["tools_json"] = None

        return create_response(data=item)

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.error(f"获取 AI Prompt 详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="获取 Prompt 详情失败"),
        )


@router.post("/prompts")
async def create_ai_prompt(
    payload: AIPromptCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """创建 AI Prompt。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        # 验证 tools_json 格式
        if payload.tools_json:
            try:
                json.loads(payload.tools_json)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_response(code=400, msg="tools_json 格式错误"),
                )

        # 如果设置为激活，先取消其他激活的 Prompt
        if payload.is_active:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{base_url}/ai_prompt?is_active=eq.true",
                    headers=headers,
                    json={"is_active": False},
                )

        # 创建新 Prompt
        prompt_data = payload.model_dump(exclude_none=True)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/ai_prompt",
                headers=headers,
                json=prompt_data,
            )
            response.raise_for_status()

        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        # 解析 tools_json
        if result.get("tools_json"):
            try:
                result["tools_json"] = json.loads(result["tools_json"])
            except (json.JSONDecodeError, TypeError):
                result["tools_json"] = None

        return create_response(data=result, msg="创建成功")

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.error(f"创建 AI Prompt 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="创建 Prompt 失败"),
        )


@router.put("/prompts/{prompt_id}")
async def update_ai_prompt(
    prompt_id: int,
    payload: AIPromptUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新 AI Prompt。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        update_data = payload.model_dump(exclude_none=True)

        # 验证 tools_json 格式
        if "tools_json" in update_data and update_data["tools_json"]:
            try:
                json.loads(update_data["tools_json"])
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=create_response(code=400, msg="tools_json 格式错误"),
                )

        # 如果设置为激活，先取消其他激活的 Prompt
        if update_data.get("is_active"):
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{base_url}/ai_prompt?is_active=eq.true&id=neq.{prompt_id}",
                    headers=headers,
                    json={"is_active": False},
                )

        # 更新 Prompt
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{base_url}/ai_prompt?id=eq.{prompt_id}",
                headers=headers,
                json=update_data,
            )
            response.raise_for_status()

        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        elif not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_response(code=404, msg="Prompt 不存在"),
            )

        # 解析 tools_json
        if result.get("tools_json"):
            try:
                result["tools_json"] = json.loads(result["tools_json"])
            except (json.JSONDecodeError, TypeError):
                result["tools_json"] = None

        return create_response(data=result, msg="更新成功")

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.error(f"更新 AI Prompt 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="更新 Prompt 失败"),
        )


@router.post("/prompts/{prompt_id}/activate")
async def activate_ai_prompt(
    prompt_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """激活 AI Prompt。"""
    try:
        base_url = get_supabase_base_url()
        headers = get_supabase_headers()

        # 先取消其他激活的 Prompt
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(
                f"{base_url}/ai_prompt?is_active=eq.true",
                headers=headers,
                json={"is_active": False},
            )

            # 激活当前 Prompt
            response = await client.patch(
                f"{base_url}/ai_prompt?id=eq.{prompt_id}",
                headers=headers,
                json={"is_active": True},
            )
            response.raise_for_status()

        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        elif not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_response(code=404, msg="Prompt 不存在"),
            )

        # 解析 tools_json
        if result.get("tools_json"):
            try:
                result["tools_json"] = json.loads(result["tools_json"])
            except (json.JSONDecodeError, TypeError):
                result["tools_json"] = None

        return create_response(data=result, msg="激活成功")

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.error(f"激活 AI Prompt 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(code=500, msg="激活 Prompt 失败"),
        )

