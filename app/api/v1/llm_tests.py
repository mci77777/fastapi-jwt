"""LLM 测试相关路由。"""

from __future__ import annotations

import secrets
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, conint

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id

from .llm_common import create_response, get_jwt_test_service, get_service

router = APIRouter(prefix="/llm", tags=["llm"])


class PromptTestRequest(BaseModel):
    """Prompt 测试请求体。"""

    prompt_id: int = Field(..., description="Prompt ID")
    endpoint_id: int = Field(..., description="接口 ID")
    message: str = Field(..., min_length=1, description="测试消息内容")
    model: str | None = Field(None, description="可选模型名称")
    skip_prompt: bool = False


class JwtDialogRequest(BaseModel):
    """JWT 对话模拟请求。"""

    prompt_id: int
    endpoint_id: int
    message: str
    model: str | None = None
    username: str | None = None
    skip_prompt: bool = False


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
    skip_prompt: bool = False


class CreateMailUserRequest(BaseModel):
    mail_api_key: Optional[str] = None
    username_prefix: str = "gymbro-test-01"
    email_domain: Optional[str] = Field(default=None, description="未配置 Mail API 时的兜底域名（默认 example.com）")


def _resolve_supabase_base_url(settings: Any) -> str:
    """解析 Supabase base URL（SSOT：优先 SUPABASE_URL，其次 SUPABASE_PROJECT_ID）。"""
    url = getattr(settings, "supabase_url", None)
    if url:
        return str(url).rstrip("/")
    project_id = getattr(settings, "supabase_project_id", None)
    if project_id:
        return f"https://{project_id}.supabase.co"
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=create_response(code=500, msg="supabase_not_configured", request_id=get_current_request_id()),
    )


def _resolve_supabase_service_key(settings: Any) -> str:
    key = getattr(settings, "supabase_service_role_key", None)
    if isinstance(key, str) and key.strip():
        return key.strip()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=create_response(code=500, msg="supabase_service_role_key_missing", request_id=get_current_request_id()),
    )


def _resolve_supabase_anon_key(settings: Any) -> str:
    # KISS：优先 anon key；若缺失，允许回退 service role（某些部署可用），避免阻断线上调试。
    anon = getattr(settings, "supabase_anon_key", None)
    if isinstance(anon, str) and anon.strip():
        return anon.strip()
    service_key = getattr(settings, "supabase_service_role_key", None)
    if isinstance(service_key, str) and service_key.strip():
        return service_key.strip()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=create_response(code=500, msg="supabase_anon_key_missing", request_id=get_current_request_id()),
    )


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
            skip_prompt=payload.skip_prompt,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg=str(exc)),
        )
    return create_response(data=result, msg="测试成功")


@router.post("/tests/create-mail-user")
async def create_mail_user(
    payload: CreateMailUserRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """通过 Mail API 创建测试用户流程（仅用于调试）。
    
    1. 生成临时邮箱
    2. (模拟) 如果有真实的注册接口，应该调用它。
       目前由于没有真实的注册接口暴露给前端，且 base.py 只有 admin 登录，
       我们这里模拟这个过程：获取邮箱 -> 生成此邮箱对应的 Token。
       这允许该用户以该邮箱身份进行 JWT 测试。
    """
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_response(code=403, msg="anonymous_user_not_allowed", request_id=get_current_request_id()),
        )

    from app.api.v1.base import create_test_jwt_token
    from app.settings.config import get_settings

    settings = get_settings()
    request_id = get_current_request_id()

    # Mail API Key：仅在 payload 显式传入时才启用（避免服务端 env 配置错误导致 UI 生成链路整体不可用）
    api_key = (payload.mail_api_key or "").strip() or None

    # MOCK MODE：仅用于 UI 冒烟（不产出 Supabase Auth 真实 JWT）
    if api_key == "test-key-mock":
        ts = int(time.time())
        username = (payload.username_prefix or "").strip() or f"mock-user-{ts}"
        password = f"mock-{secrets.token_urlsafe(12)}"
        return create_response(
            data={
                "mode": "mock",
                "email": f"{username}@example.com",
                "username": username,
                "password": password,
                "access_token": create_test_jwt_token(username),
                "token_type": "bearer",
                "note": "MOCK MODE: access_token 由本地生成，非 Supabase Auth 签发。",
            }
        )

    # 真实模式：Supabase Admin 创建用户 + password grant 换取真实 access_token
    supabase_url = _resolve_supabase_base_url(settings)
    service_key = _resolve_supabase_service_key(settings)
    anon_key = _resolve_supabase_anon_key(settings)

    username = (payload.username_prefix or "").strip() or "gymbro-test-01"
    password = secrets.token_urlsafe(18)

    email_address: str
    try:
        if api_key:
            from app.services.mail_auth_service import MailAuthService

            ms = MailAuthService(api_key=api_key)
            config = await ms.get_config()
            domains = config.get("domains") if isinstance(config, dict) else None
            if not isinstance(domains, list) or not domains:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=create_response(code=502, msg="mail_api_no_domains", request_id=request_id),
                )
            # 为避免重复/冲突，邮箱本地部分附加时间戳，但 user_metadata.username 保持稳定（便于观测与对账）
            email_name = f"{username}-{int(time.time())}"
            email_data = await ms.generate_email(domain=str(domains[0]), name=email_name)
            email_address = str(email_data.get("address") or "").strip()
            if not email_address or "@" not in email_address:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=create_response(code=502, msg="mail_api_invalid_email", request_id=request_id),
                )
        else:
            domain = (payload.email_domain or "example.com").strip() or "example.com"
            email_local = f"{username}+{int(time.time())}"
            email_address = f"{email_local}@{domain}"
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=create_response(code=502, msg="mail_api_error", request_id=request_id),
        ) from exc

    headers_service = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }
    headers_auth = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }

    create_url = f"{supabase_url}/auth/v1/admin/users"
    token_url = f"{supabase_url}/auth/v1/token?grant_type=password"

    user_id: Optional[str] = None
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        # 1) 创建用户（Admin）
        resp = await client.post(
            create_url,
            headers=headers_service,
            json={
                "email": email_address,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"username": username, "scenario": "jwt_ui_test", "created_by": "llm_tests"},
            },
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(
                    code=502,
                    msg="supabase_admin_create_user_failed",
                    request_id=request_id,
                    upstream_status=resp.status_code,
                ),
            )

        created = resp.json()
        if isinstance(created, dict):
            user_id = created.get("id") or (created.get("user") or {}).get("id")

        # 2) 换取 access_token（Password grant）
        token_resp = await client.post(
            token_url,
            headers=headers_auth,
            json={"email": email_address, "password": password},
        )
        if token_resp.status_code >= 400:
            # 尽力清理刚创建的用户（避免泄漏大量测试账号）
            if user_id:
                try:
                    await client.delete(
                        f"{supabase_url}/auth/v1/admin/users/{user_id}",
                        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}", "X-Request-Id": request_id},
                    )
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(
                    code=502,
                    msg="supabase_token_exchange_failed",
                    request_id=request_id,
                    upstream_status=token_resp.status_code,
                ),
            )

        session = token_resp.json()
        access_token = session.get("access_token") if isinstance(session, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=create_response(code=502, msg="supabase_missing_access_token", request_id=request_id),
            )

        return create_response(
            data={
                "mode": "permanent",
                "user_id": user_id,
                "email": email_address,
                "username": username,
                "password": password,
                "access_token": access_token,
                "refresh_token": session.get("refresh_token") if isinstance(session, dict) else None,
                "expires_in": session.get("expires_in") if isinstance(session, dict) else None,
                "token_type": session.get("token_type") if isinstance(session, dict) else "bearer",
            }
        )


@router.post("/tests/dialog")
async def simulate_jwt_dialog(
    payload: JwtDialogRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    try:
        result = await service.simulate_dialog(payload.model_dump())
        return create_response(data=result)
    except RuntimeError as exc:
        # AI 服务调用失败（如 API 超时、模型不存在等）
        return create_response(code=500, msg=str(exc), data={"error": str(exc)})
    except ValueError as exc:
        # 配置错误（如 prompt/endpoint 不存在）
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg=str(exc)),
        )
    except Exception as exc:
        # 未知错误 - 记录并返回
        import logging
        logging.exception("simulate_jwt_dialog error")
        return create_response(code=500, msg=f"内部错误: {exc}", data={"error": str(exc)})


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
    "CreateMailUserRequest",
]
