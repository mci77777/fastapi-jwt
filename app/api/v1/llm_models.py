"""LLM 模型相关路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id
from app.core.sse_guard import get_sse_guard
from app.db.sqlite_manager import get_sqlite_manager

from app.settings.config import get_settings
from app.services.ai_service import DEFAULT_LLM_APP_RESULT_MODE, AIService
from app.services.llm_model_registry import LlmModelRegistry

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

_DEFAULT_LLM_APP_CONFIG: dict[str, Any] = {
    # App 默认 SSE 输出模式：raw_passthrough=上游 RAW 透明转发；xml_plaintext=解析后纯文本（含 XML 标签）；auto=自动判断
    "default_result_mode": DEFAULT_LLM_APP_RESULT_MODE,
    # Agent / Tools：Web 搜索（默认关闭；可在 Dashboard 中配置）
    "web_search_enabled": False,
    "web_search_provider": "exa",
}

def _mask_secret(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}***{text[-4:]}"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    return False


class APIEndpointBase(BaseModel):
    """AI 接口公共字段。"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1)
    provider_protocol: Optional[Literal["openai", "claude"]] = Field(
        default=None,
        description="上游协议：openai=OpenAI-compatible(/v1/chat/completions)；claude=Anthropic Messages(/v1/messages)",
    )
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

async def _get_llm_app_config(request: Request) -> dict[str, Any]:
    db = get_sqlite_manager(request.app)
    rows = await db.fetchall("SELECT key, value_json FROM llm_app_settings ORDER BY key ASC", ())
    merged: dict[str, Any] = dict(_DEFAULT_LLM_APP_CONFIG)
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        raw = row.get("value_json")
        if raw is None:
            continue
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        merged[key] = value

    mode = str(merged.get("default_result_mode") or "").strip()
    if mode not in {"xml_plaintext", "raw_passthrough", "auto"}:
        mode = "raw_passthrough"
    merged["default_result_mode"] = mode

    provider = str(merged.get("web_search_provider") or "exa").strip().lower() or "exa"
    if provider != "exa":
        provider = "exa"
    merged["web_search_provider"] = provider
    merged["web_search_enabled"] = _as_bool(merged.get("web_search_enabled"))

    raw_key = merged.get("web_search_exa_api_key")
    key = str(raw_key or "").strip()
    source = "db" if key else "none"
    if not key:
        key = str(os.getenv("EXA_API_KEY") or "").strip()
        source = "env" if key else "none"
    merged.pop("web_search_exa_api_key", None)
    merged["web_search_exa_api_key_masked"] = _mask_secret(key) if key else ""
    merged["web_search_exa_api_key_source"] = source
    return merged


async def _set_llm_app_config(request: Request, values: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "default_result_mode",
        "web_search_enabled",
        "web_search_provider",
        "web_search_exa_api_key",
    }
    db = get_sqlite_manager(request.app)
    for key, value in values.items():
        if key not in allowed_keys:
            continue
        try:
            value_json = json.dumps(value, ensure_ascii=False)
        except Exception:
            value_json = json.dumps(str(value), ensure_ascii=False)
        await db.execute(
            """
            INSERT INTO llm_app_settings(key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
              value_json = excluded.value_json,
              updated_at = CURRENT_TIMESTAMP
            """,
            (str(key), value_json),
        )
    return await _get_llm_app_config(request)


@router.get("/app/config", response_model=None)
async def get_llm_app_config(
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
) -> dict[str, Any]:
    data = await _get_llm_app_config(request)
    return create_response(data=data, msg="ok")


class LlmAppConfigUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_result_mode: Literal["xml_plaintext", "raw_passthrough", "auto"] | None = Field(default=None)
    web_search_enabled: bool | None = Field(default=None)
    web_search_provider: Literal["exa"] | None = Field(default=None)
    # 注意：该字段为写入专用；读取时仅返回 masked 版本，避免泄露。
    web_search_exa_api_key: str | None = Field(default=None, min_length=0, max_length=512)


@router.post("/app/config", response_model=None)
async def upsert_llm_app_config(
    payload: LlmAppConfigUpsertRequest,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
) -> dict[str, Any]:
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    data = await _set_llm_app_config(request, values)
    return create_response(data=data, msg="updated")


@router.post("/sse/force-disconnect")
async def force_disconnect_sse(
    user_id: str | None = Query(default=None, description="目标 user_id；为空则断开当前用户"),  # noqa: B008
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """强制断开 SSE 连接（E2E/排障用）。"""

    target = str(user_id or "").strip() or current_user.uid
    guard = get_sse_guard()
    disconnected = await guard.force_disconnect_user(target)
    stats = await guard.get_stats()
    return create_response(data={"user_id": target, "disconnected": disconnected, "stats": stats}, msg="已断开")


@router.get("/app/models")
async def list_app_models(
    request: Request,
    include_inactive: bool = Query(default=False, description="是否包含非激活映射（仅调试用）"),  # noqa: B008
    debug: bool = Query(default=False, description="是否返回调试字段（仅 DEBUG=true 生效）"),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """App 侧模型列表（SSOT：/api/v1/llm/models 的白名单逻辑）。"""

    ai_service = getattr(request.app.state, "ai_service", None)
    if not isinstance(ai_service, AIService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI service unavailable"),
        )

    settings = get_settings()
    allow_debug = bool(debug) and (getattr(settings, "debug", False) or is_dashboard_admin_user(current_user))

    items = await ai_service.list_app_model_scopes(
        include_inactive=bool(include_inactive),
        include_debug_fields=allow_debug,
    )

    # 兼容旧 schema：同时返回 model（=name）
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        copy = dict(item)
        copy.setdefault("model", name)
        normalized.append(copy)

    recommended_model = normalized[0].get("name") if normalized else None
    return create_response(
        data=normalized,
        total=len(normalized),
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
    scope_type: Optional[str] = Query(default=None, description="映射 scope_type 过滤（view=mapped 生效）"),  # noqa: B008
    scope_key: Optional[str] = Query(default=None, description="映射 scope_key 过滤（view=mapped 生效）"),  # noqa: B008
    keyword: Optional[str] = Query(default=None, description="关键词"),  # noqa: B008
    only_active: Optional[bool] = Query(default=None, description="是否仅活跃"),  # noqa: B008
    refresh_missing_models: bool = Query(
        default=False,
        description="是否刷新缺失的 model_list（会触发上游 models 探测：OpenAI → Claude 兜底）",
    ),  # noqa: B008
    page: int = Query(default=1, ge=1),  # noqa: B008
    page_size: int = Query(default=20, ge=1, le=100),  # noqa: B008
    debug: bool = Query(default=False, description="是否返回调试字段（仅 DEBUG=true 或管理员生效）"),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    # endpoints 视图仅供管理后台使用，避免 App 误用导致“看到全部供应商模型列表”。
    # 若非管理员请求 endpoints，则降级为 mapped（安全且兼容）。
    if view == "endpoints":
        try:
            await require_llm_admin(current_user=current_user)
        except HTTPException:
            view = "mapped"

    if view == "mapped":
        ai_service = getattr(request.app.state, "ai_service", None)
        if not isinstance(ai_service, AIService):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=create_response(code=503, msg="AI service unavailable"),
            )

        settings = get_settings()
        allow_debug = bool(debug) and (getattr(settings, "debug", False) or is_dashboard_admin_user(current_user))
        include_inactive = not (True if only_active is None else bool(only_active))

        items = await ai_service.list_app_model_scopes(
            include_inactive=include_inactive,
            include_debug_fields=allow_debug,
        )

        registry = getattr(request.app.state, "llm_model_registry", None)
        if isinstance(registry, LlmModelRegistry):
            enriched: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                copy = dict(item)
                # 稳定 schema：字段存在但允许为 null（resolve 失败时不阻塞列表）
                copy.setdefault("provider", None)
                copy.setdefault("dialect", None)
                copy.setdefault("capabilities", None)
                copy.setdefault("endpoint_hint", None)
                try:
                    route = await registry.resolve_model_key(name)
                    copy["provider"] = route.provider
                    copy["dialect"] = route.dialect
                    copy["capabilities"] = registry.infer_capabilities(route)
                    copy["endpoint_hint"] = {
                        "endpoint_id": route.endpoint_id,
                        "endpoint_name": route.endpoint.get("name"),
                    }
                except Exception:
                    # 不阻塞列表：缺失字段按旧 schema 兼容
                    pass
                enriched.append(copy)
            items = enriched

        # 兼容：对 mapped 视图保留 keyword 过滤（按 name / default_model / candidates）
        keyword_text = str(keyword or "").strip().lower()
        if keyword_text:
            filtered: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                candidates_value = item.get("candidates") or []
                candidates_text = " ".join([str(x) for x in candidates_value]) if isinstance(candidates_value, list) else ""
                haystack = " ".join([str(item.get("name") or ""), str(item.get("default_model") or ""), candidates_text]).lower()
                if keyword_text in haystack:
                    filtered.append(item)
            items = filtered

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
        # KISS：避免 Dashboard 首屏“批量打爆上游”，每次请求最多刷新 1 个缺失项。
        to_refresh = to_refresh[:1]
        refreshed = False
        for ep in to_refresh:
            try:
                await service.refresh_endpoint_status(int(ep["id"]))
                refreshed = True
            except Exception:
                # 不中断列表返回：失败信息会写入 last_error/status
                continue

        if refreshed:
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


@router.get("/models/registry")
async def list_model_registry(
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """聚合后的“模型 -> 上游配置”视图（仅管理员/内部排障）。"""

    ai_service = getattr(request.app.state, "ai_service", None)
    if not isinstance(ai_service, AIService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="AI service unavailable"),
        )

    registry = getattr(request.app.state, "llm_model_registry", None)
    if not isinstance(registry, LlmModelRegistry):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_response(code=503, msg="Model registry unavailable"),
        )

    items = await ai_service.list_app_model_scopes(include_inactive=True, include_debug_fields=True)
    resolved: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            route = await registry.resolve_model_key(name)
        except Exception:
            continue
        resolved.append(
            {
                "name": name,
                "provider": route.provider,
                "dialect": route.dialect,
                "capabilities": registry.infer_capabilities(route),
                "real_model": route.resolved_model,
                "base_url": route.endpoint.get("base_url"),
                "endpoint_id": route.endpoint_id,
                "endpoint_name": route.endpoint.get("name"),
            }
        )

    return create_response(data=resolved, total=len(resolved))


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
    monitor = get_monitor(request)
    monitor.trigger_probe()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=create_response(
            data=monitor.snapshot(),
            code=status.HTTP_202_ACCEPTED,
            msg="已触发批量检测",
        ),
    )


@router.get("/models/check-all")
async def check_all_endpoints_get(
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    monitor = get_monitor(request)
    monitor.trigger_probe()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=create_response(
            data=monitor.snapshot(),
            code=status.HTTP_202_ACCEPTED,
            msg="已触发批量检测",
        ),
    )


@router.get("/models/{endpoint_id}")
async def get_ai_model(
    endpoint_id: int,
    request: Request,
    _: None = Depends(require_llm_admin),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        endpoint = await service.get_endpoint(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="接口不存在"),
        )
    return create_response(data=endpoint)


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
