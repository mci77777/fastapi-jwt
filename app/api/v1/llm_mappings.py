"""LLM 模型映射路由。"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user

from .llm_common import SyncDirection, SyncRequest, create_response, get_mapping_service, require_llm_admin

router = APIRouter(prefix="/llm", tags=["llm"])


class ModelMappingPayload(BaseModel):
    """模型映射配置。

    业务域类型说明：
    - user: 普通用户（默认）- 只能访问基础模型（如 GPT-3.5）
    - premium_user: 高级用户 - 可访问高级模型（如 GPT-4、Claude-3）
    - mapping: 映射名（App/Web 业务 key）- 用于把“客户端可发送的 model”路由到真实上游模型
    - global: 全局 - 系统级配置

    兼容：tenant 作为 mapping 的历史别名，后端会在写入/解析时做归一化。
    """

    scope_type: str = Field(
        default="user",
        description="业务域类型：user/premium_user/mapping/global（prompt/module 也可用于内部映射）",
    )
    scope_key: str = Field(..., description="业务域唯一标识")
    name: Optional[str] = Field(None, description="业务域名称")
    default_model: Optional[str] = Field(None, description="默认模型")
    candidates: list[str] = Field(default_factory=list, description="可用模型集合")
    is_active: bool = Field(default=True, description="是否启用")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class ActivateMappingRequest(BaseModel):
    """切换默认模型请求体。"""

    default_model: str = Field(..., description="新的默认模型")


@router.get("/model-groups")
async def list_model_groups(
    request: Request,
    scope_type: str | None = None,
    scope_key: str | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_mapping_service(request)
    mappings = await service.list_mappings(scope_type=scope_type, scope_key=scope_key)
    return create_response(data=mappings)


@router.post("/model-groups")
async def upsert_model_group(
    payload: ModelMappingPayload,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_mapping_service(request)
    mapping = await service.upsert_mapping(payload.model_dump())
    return create_response(data=mapping, msg="保存成功")


@router.post("/model-groups/{mapping_id}/activate")
async def activate_model_group(
    mapping_id: str,
    payload: ActivateMappingRequest,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_mapping_service(request)
    mapping = await service.activate_default(mapping_id, payload.default_model)
    return create_response(data=mapping, msg="默认模型已更新")


@router.delete("/model-groups/{mapping_id}")
async def delete_model_group(
    mapping_id: str,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_mapping_service(request)
    try:
        deleted = await service.delete_mapping(mapping_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_response(code=422, msg=str(exc)),
        ) from exc
    return create_response(data={"deleted": deleted, "id": mapping_id}, msg="已删除" if deleted else "不存在")


@router.post("/model-groups/sync-to-supabase")
async def sync_mappings_to_supabase(
    request: Request,
    delete_missing: bool = False,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """同步所有模型映射到 Supabase。

    将当前所有模型映射关系批量同步到 Supabase 数据库的 model_mappings 表。
    注意：此操作会覆盖 Supabase 中的现有映射数据。
    """
    service = get_mapping_service(request)
    try:
        result = await service.sync_to_supabase(delete_missing=bool(delete_missing))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=result, msg=f"已同步 {result.get('synced_count', 0)} 条映射到 Supabase")


@router.post("/model-groups/sync")
async def sync_model_groups(
    request: Request,
    body: SyncRequest | None = None,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """模型映射双向同步（push/pull）。

    - push：本地 SQLite -> Supabase model_mappings
    - pull：Supabase model_mappings -> 本地 SQLite（仅 scope_type != prompt）
    """

    service = get_mapping_service(request)
    payload = body or SyncRequest()
    direction = payload.direction
    try:
        result: dict[str, Any] = {}
        if direction in (SyncDirection.PUSH, SyncDirection.BOTH):
            result["push"] = await service.sync_to_supabase(delete_missing=payload.delete_missing)
        if direction in (SyncDirection.PULL, SyncDirection.BOTH):
            result["pull"] = await service.sync_from_supabase(
                overwrite=payload.overwrite,
                delete_missing=payload.delete_missing,
            )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg=str(exc)),
        ) from exc
    return create_response(data=result, msg=f"模型映射同步完成({direction.value})")


@router.post("/model-groups/import-local-json")
async def import_local_model_groups(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """从本地 JSON 文件导入模型映射（upsert，不删除）。"""

    try:
        raw = await file.read()
    finally:
        await file.close()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig", errors="ignore")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_response(code=422, msg="invalid_json"),
        ) from exc

    mappings: Any = None
    if isinstance(payload, dict):
        mappings = payload.get("mappings")
    elif isinstance(payload, list):
        mappings = payload

    if not isinstance(mappings, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_response(code=422, msg="invalid_mappings_payload"),
        )

    service = get_mapping_service(request)
    result = await service.import_local_mappings(mappings)
    return create_response(
        data=result,
        msg=f"导入完成：成功 {result.get('imported_count', 0)} 条，跳过 {result.get('skipped_count', 0)} 条",
    )


__all__ = ["router", "ModelMappingPayload", "ActivateMappingRequest"]
