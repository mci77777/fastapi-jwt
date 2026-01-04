"""LLM 模型相关路由。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id

from app.settings.config import get_settings

from .llm_common import (
    SyncDirection,
    SyncRequest,
    create_response,
    get_mapping_service,
    get_monitor,
    get_service,
    is_dashboard_admin_user,
    require_llm_admin,
)

router = APIRouter(prefix="/llm", tags=["llm"])
logger = logging.getLogger(__name__)


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


class BlockedModelUpdate(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)
    blocked: bool = Field(default=True)


class BlockedModelsUpdateRequest(BaseModel):
    updates: list[BlockedModelUpdate] = Field(default_factory=list)


@router.get("/app/models")
async def list_app_models(
    request: Request,
    include_inactive: bool = Query(default=False, description="是否包含非激活映射（仅调试用）"),  # noqa: B008
    debug: bool = Query(default=False, description="是否返回调试字段（仅 DEBUG=true 生效）"),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """App 侧模型列表（返回“映射模型 key”，避免客户端直接选择供应商原始 model）。"""

    mapping_service = get_mapping_service(request)
    settings = get_settings()
    blocked_models = set(await mapping_service.list_blocked_models())
    allow_debug = bool(debug) and (getattr(settings, "debug", False) or is_dashboard_admin_user(current_user))

    try:
        all_mappings = await mapping_service.list_mappings()
    except Exception:
        all_mappings = []

    # App 端到端兜底：若没有任何映射，自动种一个最小 global 映射，避免 “可选模型为空” 导致对话无法选择模型。
    if not all_mappings:
        try:
            await mapping_service.ensure_minimal_global_mapping()
            all_mappings = await mapping_service.list_mappings()
        except Exception:
            all_mappings = []

    candidates: list[dict[str, Any]] = []
    for mapping in all_mappings:
        if not isinstance(mapping, dict):
            continue
        scope_type = mapping.get("scope_type")
        scope_key = mapping.get("scope_key")
        if scope_type == "user" and scope_key != current_user.uid:
            continue
        if scope_type == "global" and scope_key != "global":
            continue
        if scope_type not in {"user", "global"}:
            continue

        is_active = bool(mapping.get("is_active", True))
        if not include_inactive and not is_active:
            continue

        model_key = mapping.get("id")
        if not isinstance(model_key, str) or not model_key.strip():
            continue
        model_key = model_key.strip()

        candidates_list = mapping.get("candidates") if isinstance(mapping.get("candidates"), list) else []
        filtered_candidates = [
            item
            for item in candidates_list
            if isinstance(item, str) and item.strip() and item.strip() not in blocked_models
        ]

        resolved_model = mapping.get("default_model")
        if isinstance(resolved_model, str):
            resolved_model = resolved_model.strip()
        if not isinstance(resolved_model, str) or not resolved_model or resolved_model in blocked_models:
            resolved_model = filtered_candidates[0] if filtered_candidates else None

        # 无可用真实模型：该映射对 App 无意义（且可能会把 mapping key 直打上游），直接过滤掉
        if resolved_model is None:
            continue

        item: dict[str, Any] = {
            "model": model_key,
            "label": (mapping.get("name") or model_key).strip()
            if isinstance(mapping.get("name") or model_key, str)
            else model_key,
            "scope_type": scope_type,
        }

        if allow_debug:
            item.update(
                {
                    "resolved_model": resolved_model,
                    "candidates": filtered_candidates,
                    "blocked_candidates": sorted(
                        {
                            str(value).strip()
                            for value in candidates_list
                            if isinstance(value, str) and value.strip() and value.strip() in blocked_models
                        }
                    ),
                    "updated_at": mapping.get("updated_at"),
                    "source": mapping.get("source"),
                }
            )

        candidates.append(item)

    # 去重并保持顺序（user 优先于 global）
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(candidates, key=lambda x: 0 if x.get("scope_type") == "user" else 1):
        model_key = str(item.get("model") or "")
        if not model_key or model_key in seen:
            continue
        seen.add(model_key)
        deduped.append(item)

    recommended_model = deduped[0]["model"] if deduped else None

    return create_response(
        data=deduped,
        total=len(deduped),
        recommended_model=recommended_model,
    )


@router.get("/models/blocked")
async def list_blocked_models(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    mapping_service = get_mapping_service(request)
    blocked = await mapping_service.list_blocked_models()
    return create_response(data={"blocked": blocked, "total": len(blocked)})


@router.put("/models/blocked")
async def upsert_blocked_models(
    payload: BlockedModelsUpdateRequest,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    mapping_service = get_mapping_service(request)
    updates = [item.model_dump(mode="python") for item in payload.updates]
    blocked = await mapping_service.upsert_blocked_models(updates)
    return create_response(data={"blocked": blocked, "total": len(blocked)}, msg="已更新")


@router.get("/models")
async def list_ai_models(
    request: Request,
    view: Literal["mapped", "endpoints"] = Query(  # noqa: B008
        default="mapped",
        description="视图：mapped=返回映射后的标准模型；endpoints=返回供应商 endpoint 列表（管理后台用）",
    ),
    scope_type: str = Query(default="tenant", description="映射 scope_type（view=mapped 生效）"),  # noqa: B008
    scope_key: Optional[str] = Query(default=None, description="映射 scope_key（view=mapped 可选过滤）"),  # noqa: B008
    keyword: Optional[str] = Query(default=None, description="关键词"),  # noqa: B008
    only_active: Optional[bool] = Query(default=None, description="是否仅活跃"),  # noqa: B008
    refresh_missing_models: bool = Query(default=False, description="是否刷新缺失的 model_list（会触发 /v1/models 探测）"),  # noqa: B008
    page: int = Query(default=1, ge=1),  # noqa: B008
    page_size: int = Query(default=20, ge=1, le=100),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    if view == "mapped":
        mapping_service = get_mapping_service(request)
        blocked_models = set(await mapping_service.list_blocked_models())

        # 契约默认：只返回启用映射
        active_only = True if only_active is None else bool(only_active)

        try:
            mappings = await mapping_service.list_mappings(scope_type=scope_type, scope_key=scope_key)
        except Exception:
            mappings = []

        keyword_text = str(keyword or "").strip().lower()

        items: list[dict[str, Any]] = []
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue

            is_active = bool(mapping.get("is_active", True))
            if active_only and not is_active:
                continue

            mapping_scope_type = str(mapping.get("scope_type") or "").strip()
            mapping_scope_key = str(mapping.get("scope_key") or "").strip()
            if not mapping_scope_type or not mapping_scope_key:
                continue

            name = mapping.get("name")
            display_name = str(name).strip() if isinstance(name, str) and name.strip() else mapping_scope_key

            raw_candidates = mapping.get("candidates") if isinstance(mapping.get("candidates"), list) else []
            candidates: list[str] = []
            for value in raw_candidates:
                text = str(value or "").strip()
                if not text or text in blocked_models or text in candidates:
                    continue
                candidates.append(text)

            raw_default = mapping.get("default_model")
            default_model = str(raw_default).strip() if isinstance(raw_default, str) else ""
            if default_model and default_model not in blocked_models and default_model not in candidates:
                candidates.insert(0, default_model)

            # 若 default 被屏蔽/为空，则用首个可用 candidates 作为“有效 default”
            effective_default = candidates[0] if candidates else None
            if effective_default is None:
                continue

            if keyword_text:
                haystack = " ".join(
                    [
                        display_name,
                        mapping_scope_type,
                        mapping_scope_key,
                        effective_default,
                    ]
                ).lower()
                if keyword_text not in haystack:
                    continue

            items.append(
                {
                    "name": display_name,
                    "scope_type": mapping_scope_type,
                    "scope_key": mapping_scope_key,
                    "default_model": effective_default,
                    "candidates": candidates,
                    "candidates_count": len(candidates),
                    "updated_at": mapping.get("updated_at"),
                }
            )

        return create_response(
            data=items,
            total=len(items),
        )

    service = get_service(request)
    items, total = await service.list_endpoints(
        keyword=keyword,
        only_active=only_active,
        page=page,
        page_size=page_size,
    )

    # /ai/jwt 需要可选模型：当端点来自 Supabase pull 时，model_list 默认为空（Supabase 不存此字段）。
    # 这里按需刷新缺失项并落盘，避免用户每次刷新只剩 “1 个默认模型”。
    if refresh_missing_models and items:
        to_refresh = [
            endpoint
            for endpoint in items
            if endpoint
            and not (endpoint.get("model_list") or [])
            and endpoint.get("has_api_key")
            and endpoint.get("is_active")
        ]
        # KISS：限制并发与数量，避免一次页面加载阻塞太久
        to_refresh = to_refresh[:10]
        sem = asyncio.Semaphore(5)

        async def _refresh_one(endpoint_id: int) -> None:
            async with sem:
                try:
                    await service.refresh_endpoint_status(endpoint_id)
                except Exception:
                    # 不中断列表返回：失败信息会写入 last_error/status
                    return

        tasks = []
        for ep in to_refresh:
            try:
                tasks.append(asyncio.create_task(_refresh_one(int(ep["id"]))))
            except Exception:
                continue

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
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
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    logger.info(
        "LLM endpoint create user_id=%s name=%s base_url=%s is_default=%s request_id=%s",
        current_user.uid,
        payload.name,
        payload.base_url,
        bool(payload.is_default),
        get_current_request_id(),
    )
    service = get_service(request)
    try:
        endpoint = await service.create_endpoint(
            payload.model_dump(exclude={"auto_sync"}, exclude_none=True),
            auto_sync=payload.auto_sync,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_response(code=400, msg=code),
        ) from exc
    return create_response(data=endpoint, msg="创建成功")


@router.put("/models")
async def update_ai_model(
    payload: AIModelUpdate,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    logger.info(
        "LLM endpoint update user_id=%s endpoint_id=%s is_default=%s request_id=%s",
        current_user.uid,
        payload.id,
        bool(payload.is_default),
        get_current_request_id(),
    )
    service = get_service(request)
    try:
        endpoint = await service.update_endpoint(
            payload.id,
            payload.model_dump(
                exclude={"id", "auto_sync"},
                exclude_none=True,
            ),
        )
    except ValueError as exc:
        if str(exc) == "endpoint_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_response(code=404, msg="接口不存在"),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_response(code=400, msg=str(exc)),
        ) from exc
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
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    logger.info(
        "LLM endpoint delete user_id=%s endpoint_id=%s request_id=%s",
        current_user.uid,
        endpoint_id,
        get_current_request_id(),
    )
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
    _: None = Depends(require_llm_admin),  # noqa: B008
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
    _: None = Depends(require_llm_admin),  # noqa: B008
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
    _: None = Depends(require_llm_admin),  # noqa: B008
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
    _: None = Depends(require_llm_admin),  # noqa: B008
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
async def supabase_status(request: Request) -> dict[str, Any]:
    """
    获取 Supabase 连接状态（公开端点，无需认证）。

    返回 Supabase REST API 的连接状态、延迟和最近同步时间。
    此端点用于 Dashboard 公开页面的状态监控，不涉及敏感数据。

    注意：此端点已配置为公开访问，无需 JWT 认证。
    """
    service = get_service(request)
    status_payload = await service.supabase_status()
    return create_response(data=status_payload)


@router.get("/monitor/status")
async def monitor_status(
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    monitor = get_monitor(request)
    return create_response(data=monitor.snapshot())


@router.post("/monitor/start")
async def start_monitor(
    payload: MonitorControlRequest,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
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
    _: None = Depends(require_llm_admin),  # noqa: B008
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
