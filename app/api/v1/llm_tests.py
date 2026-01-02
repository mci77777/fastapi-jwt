"""LLM 测试相关路由。"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, conint

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id
from app.db import get_sqlite_manager

from .llm_common import create_response, get_jwt_test_service, get_service

router = APIRouter(prefix="/llm", tags=["llm"])

# Cloudflare 会对 5xx（尤其 502/503）返回 HTML 错误页，导致前端拿不到 JSON 的 request_id/hint。
# 这里用 424 Failed Dependency 表达“上游依赖不可用”，同时保留 payload.code 作为机器可读错误码。
UPSTREAM_FAILED_STATUS = status.HTTP_424_FAILED_DEPENDENCY


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
    force_new: bool = Field(default=False, description="是否强制新建（默认优先复用本地已保存用户并 refresh）")


class CreateAnonTokenRequest(BaseModel):
    """生成/复用匿名 JWT（供 Web JWT 测试页使用）。"""

    refresh_token: Optional[str] = Field(default=None, description="可选：用于当日复用的 refresh_token")
    force_new: bool = Field(default=False, description="是否强制新建匿名用户")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _anon_day_label() -> str:
    # SSOT：按 UTC 天做“当日复用”，避免跨时区部署产生歧义。
    day = datetime.now(timezone.utc).date().isoformat()
    return f"anon-{day}"


async def _persist_mail_test_user(
    request: Request,
    *,
    label: str,
    email: str,
    username: str,
    supabase_user_id: str | None,
    password: str | None,
    refresh_token: str | None,
    meta: dict[str, Any] | None = None,
    touch_used: bool = True,
    touch_refreshed: bool = False,
) -> int:
    db = get_sqlite_manager(request.app)
    meta_json = None
    if isinstance(meta, dict) and meta:
        import json

        meta_json = json.dumps(meta, ensure_ascii=False)

    used_at = _utc_now_iso() if touch_used else None
    refreshed_at = _utc_now_iso() if touch_refreshed else None

    await db.execute(
        """
        INSERT INTO llm_test_users
          (kind, label, email, username, supabase_user_id, password, refresh_token, meta_json, last_used_at, last_refreshed_at)
        VALUES
          ('mail', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
          label = excluded.label,
          username = excluded.username,
          supabase_user_id = excluded.supabase_user_id,
          password = excluded.password,
          refresh_token = excluded.refresh_token,
          meta_json = excluded.meta_json,
          last_used_at = COALESCE(excluded.last_used_at, llm_test_users.last_used_at),
          last_refreshed_at = COALESCE(excluded.last_refreshed_at, llm_test_users.last_refreshed_at)
        """,
        (
            label,
            email,
            username,
            supabase_user_id,
            password,
            refresh_token,
            meta_json,
            used_at,
            refreshed_at,
        ),
    )

    row = await db.fetchone("SELECT id FROM llm_test_users WHERE kind = 'mail' AND email = ? LIMIT 1", (email,))
    if not row or not row.get("id"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_response(
                code=500,
                msg="persist_test_user_failed",
                message="persist_test_user_failed",
                request_id=get_current_request_id(),
            ),
        )
    return int(row["id"])


async def _list_mail_test_users(request: Request, *, limit: int = 50) -> list[dict[str, Any]]:
    db = get_sqlite_manager(request.app)
    rows = await db.fetchall(
        """
        SELECT id, label, email, username, supabase_user_id, created_at, last_used_at, last_refreshed_at, refresh_token
        FROM llm_test_users
        WHERE kind = 'mail'
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        refresh_token = row.get("refresh_token")
        items.append(
            {
                "id": row.get("id"),
                "label": row.get("label"),
                "email": row.get("email"),
                "username": row.get("username"),
                "user_id": row.get("supabase_user_id"),
                "created_at": row.get("created_at"),
                "last_used_at": row.get("last_used_at"),
                "last_refreshed_at": row.get("last_refreshed_at"),
                "has_refresh_token": bool(isinstance(refresh_token, str) and refresh_token.strip()),
            }
        )
    return items


async def _get_mail_test_user_by_id(request: Request, test_user_id: int) -> dict[str, Any] | None:
    db = get_sqlite_manager(request.app)
    return await db.fetchone(
        """
        SELECT id, label, email, username, supabase_user_id, password, refresh_token, created_at
        FROM llm_test_users
        WHERE kind = 'mail' AND id = ?
        LIMIT 1
        """,
        (test_user_id,),
    )


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
        detail=create_response(
            code=500,
            msg="supabase_not_configured",
            message="supabase_not_configured",
            request_id=get_current_request_id(),
        ),
    )


def _resolve_supabase_service_key(settings: Any) -> str:
    key = getattr(settings, "supabase_service_role_key", None)
    if isinstance(key, str) and key.strip():
        return key.strip()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=create_response(
            code=500,
            msg="supabase_service_role_key_missing",
            message="supabase_service_role_key_missing",
            request_id=get_current_request_id(),
        ),
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
        detail=create_response(
            code=500,
            msg="supabase_anon_key_missing",
            message="supabase_anon_key_missing",
            request_id=get_current_request_id(),
        ),
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
            detail=create_response(
                code=403,
                msg="anonymous_user_not_allowed",
                message="anonymous_user_not_allowed",
                request_id=get_current_request_id(),
            ),
        )

    from app.api.v1.base import create_test_jwt_token
    from app.settings.config import get_settings

    settings = get_settings()
    request_id = get_current_request_id()

    # Mail API Key：优先 payload，其次服务端环境变量（线上 SSOT，避免把 key 暴露到浏览器）
    api_key = (payload.mail_api_key or settings.mail_api_key or "").strip() or None

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

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_response(
                code=500,
                msg="mail_api_key_missing",
                message="mail_api_key_missing",
                request_id=request_id,
                hint="请在后端环境变量配置 MAIL_API_KEY（可选：MAIL_API_BASE_URL/MAIL_DOMAIN/MAIL_EXPIRY_MS）。",
            ),
        )

    # 真实模式：Supabase Admin 创建用户 + password grant 换取真实 access_token
    supabase_url = _resolve_supabase_base_url(settings)
    service_key = _resolve_supabase_service_key(settings)
    anon_key = _resolve_supabase_anon_key(settings)

    username = (payload.username_prefix or "").strip() or "gymbro-test-01"

    # 默认优先复用本地已保存用户：refresh_token -> access_token（避免无限创建测试用户）
    if not payload.force_new:
        db = get_sqlite_manager(request.app)
        existing = await db.fetchone(
            """
            SELECT id, email, username, supabase_user_id, password, refresh_token
            FROM llm_test_users
            WHERE kind = 'mail' AND label = ? AND refresh_token IS NOT NULL AND TRIM(refresh_token) != ''
            ORDER BY id DESC
            LIMIT 1
            """,
            (username,),
        )
        if existing and isinstance(existing.get("refresh_token"), str) and existing["refresh_token"].strip():
            refresh_url = f"{supabase_url}/auth/v1/token?grant_type=refresh_token"
            headers_auth = {
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
                "Content-Type": "application/json",
                "X-Request-Id": request_id,
            }
            try:
                async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                    resp = await client.post(
                        refresh_url, headers=headers_auth, json={"refresh_token": existing["refresh_token"]}
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    access_token = data.get("access_token") if isinstance(data, dict) else None
                    if isinstance(access_token, str) and access_token:
                        new_refresh = data.get("refresh_token") if isinstance(data, dict) else None
                        await _persist_mail_test_user(
                            request,
                            label=username,
                            email=str(existing.get("email") or ""),
                            username=str(existing.get("username") or username),
                            supabase_user_id=existing.get("supabase_user_id"),
                            password=existing.get("password"),
                            refresh_token=new_refresh if isinstance(new_refresh, str) and new_refresh.strip() else existing["refresh_token"],
                            meta={"note": "refreshed_existing"},
                            touch_used=True,
                            touch_refreshed=True,
                        )
                        return create_response(
                            data={
                                "mode": "permanent",
                                "test_user_id": existing.get("id"),
                                "user_id": existing.get("supabase_user_id"),
                                "email": existing.get("email"),
                                "username": existing.get("username") or username,
                                "password": existing.get("password"),
                                "access_token": access_token,
                                "refresh_token": new_refresh or existing["refresh_token"],
                                "expires_in": data.get("expires_in") if isinstance(data, dict) else None,
                                "token_type": data.get("token_type") if isinstance(data, dict) else "bearer",
                                "note": "refreshed_existing",
                            }
                        )
            except Exception:
                # refresh 失败则回退到新建
                pass

    password = secrets.token_urlsafe(18)

    email_address: str
    note_extra: dict[str, Any] = {}
    domain = (payload.email_domain or "example.com").strip() or "example.com"
    email_local = f"{username}+{int(time.time())}"
    email_address = f"{email_local}@{domain}"

    # Mail API 作为“真实用户标准”：必须成功生成邮箱，否则直接报错。
    try:
        from app.services.mail_auth_service import MailAuthService

        ms = MailAuthService(api_key=api_key)
        domain_override = (getattr(settings, "mail_domain", None) or "").strip() or None
        email_name = f"{username}-{int(time.time())}"
        email_data = await ms.generate_email(
            domain=domain_override,
            name=email_name,
            expiry_ms=int(getattr(settings, "mail_expiry_ms", 3600000) or 3600000),
        )
        email_address = str(email_data.get("address") or "").strip()
        if not email_address or "@" not in email_address:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="mail_api_invalid_email",
                    message="mail_api_invalid_email",
                    request_id=request_id,
                    hint="Mail API 返回的 address 无效；请检查 MAIL_DOMAIN 或 Mail API 配置（见 docs/mail-api.txt）。",
                ),
            )
        note_extra["mail_api"] = "ok"
        note_extra["mail_api_domain"] = email_address.split("@", 1)[1]
    except HTTPException:
        raise
    except Exception as exc:
        upstream_status = None
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            upstream_status = exc.response.status_code
        raise HTTPException(
            status_code=UPSTREAM_FAILED_STATUS,
            detail=create_response(
                code=502,
                msg="mail_api_error",
                message="mail_api_error",
                request_id=request_id,
                upstream_status=upstream_status,
                hint="Mail API 请求失败；请检查 MAIL_API_KEY/MAIL_API_BASE_URL 是否正确（见 docs/mail-api.txt）。",
            ),
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
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_admin_create_user_failed",
                    message="supabase_admin_create_user_failed",
                    request_id=request_id,
                    upstream_status=resp.status_code,
                    hint="Supabase Admin 创建用户失败；请检查 SUPABASE_SERVICE_ROLE_KEY/SUPABASE_URL 是否正确，且该 key 具备 admin.users 权限。",
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
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_token_exchange_failed",
                    message="supabase_token_exchange_failed",
                    request_id=request_id,
                    upstream_status=token_resp.status_code,
                    hint="Supabase 换取 access_token 失败；请检查 SUPABASE_ANON_KEY/SUPABASE_URL，并确认 Auth 支持 email/password grant。",
                ),
            )

        session = token_resp.json()
        access_token = session.get("access_token") if isinstance(session, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_missing_access_token",
                    message="supabase_missing_access_token",
                    request_id=request_id,
                    hint="Supabase 响应缺少 access_token；请检查 Auth 配置与上游响应（建议用 request_id 追踪）。",
                ),
            )

        refresh_token = session.get("refresh_token") if isinstance(session, dict) else None
        test_user_id = await _persist_mail_test_user(
            request,
            label=username,
            email=email_address,
            username=username,
            supabase_user_id=user_id,
            password=password,
            refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token.strip() else None,
            meta=note_extra,
            touch_used=True,
            touch_refreshed=False,
        )

        return create_response(
            data={
                "mode": "permanent",
                "test_user_id": test_user_id,
                "user_id": user_id,
                "email": email_address,
                "username": username,
                "password": password,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": session.get("expires_in") if isinstance(session, dict) else None,
                "token_type": session.get("token_type") if isinstance(session, dict) else "bearer",
                **note_extra,
            },
        )


@router.get("/tests/mail-users")
async def list_mail_users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_response(
                code=403,
                msg="anonymous_user_not_allowed",
                message="anonymous_user_not_allowed",
                request_id=get_current_request_id(),
            ),
        )

    items = await _list_mail_test_users(request, limit=int(limit))
    return create_response(data={"items": items, "total": len(items)})


@router.post("/tests/mail-users/{test_user_id}/refresh")
async def refresh_mail_user_token(
    test_user_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_response(
                code=403,
                msg="anonymous_user_not_allowed",
                message="anonymous_user_not_allowed",
                request_id=get_current_request_id(),
            ),
        )

    from app.settings.config import get_settings

    settings = get_settings()
    request_id = get_current_request_id()

    row = await _get_mail_test_user_by_id(request, int(test_user_id))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(
                code=404,
                msg="test_user_not_found",
                message="test_user_not_found",
                request_id=request_id,
            ),
        )

    refresh_token = row.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_response(
                code=400,
                msg="refresh_token_missing",
                message="refresh_token_missing",
                request_id=request_id,
                hint="该测试用户未保存 refresh_token；请点击“一键生成测试用户”重新创建。",
            ),
        )

    supabase_url = _resolve_supabase_base_url(settings)
    anon_key = _resolve_supabase_anon_key(settings)
    headers_auth = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }

    refresh_url = f"{supabase_url}/auth/v1/token?grant_type=refresh_token"
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.post(refresh_url, headers=headers_auth, json={"refresh_token": refresh_token})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_refresh_failed",
                    message="supabase_refresh_failed",
                    request_id=request_id,
                    upstream_status=resp.status_code,
                    hint="refresh_token 可能已失效；请点击“一键生成测试用户”强制新建。",
                ),
            )

        data = resp.json()
        access_token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_missing_access_token",
                    message="supabase_missing_access_token",
                    request_id=request_id,
                ),
            )

        new_refresh = data.get("refresh_token") if isinstance(data, dict) else None
        await _persist_mail_test_user(
            request,
            label=str(row.get("label") or row.get("username") or "gymbro-test"),
            email=str(row.get("email") or ""),
            username=str(row.get("username") or ""),
            supabase_user_id=row.get("supabase_user_id"),
            password=row.get("password"),
            refresh_token=new_refresh if isinstance(new_refresh, str) and new_refresh.strip() else refresh_token,
            meta={"note": "refreshed_by_id"},
            touch_used=True,
            touch_refreshed=True,
        )

        return create_response(
            data={
                "mode": "permanent",
                "test_user_id": int(test_user_id),
                "user_id": row.get("supabase_user_id"),
                "email": row.get("email"),
                "username": row.get("username"),
                "password": row.get("password"),
                "access_token": access_token,
                "refresh_token": new_refresh or refresh_token,
                "expires_in": data.get("expires_in") if isinstance(data, dict) else None,
                "token_type": data.get("token_type") if isinstance(data, dict) else "bearer",
                "note": "refreshed",
            }
        )


@router.post("/tests/anon-token")
async def create_anon_token(
    payload: CreateAnonTokenRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """生成或复用匿名 JWT（真实 Supabase Auth 签发）。"""

    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_response(
                code=403,
                msg="anonymous_user_not_allowed",
                message="anonymous_user_not_allowed",
                request_id=get_current_request_id(),
            ),
        )

    from app.settings.config import get_settings

    settings = get_settings()
    request_id = get_current_request_id()

    supabase_url = _resolve_supabase_base_url(settings)
    anon_key = _resolve_supabase_anon_key(settings)

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        db = get_sqlite_manager(request.app)
        today_label = _anon_day_label()

        existing = await db.fetchone(
            """
            SELECT id, refresh_token, supabase_user_id
            FROM llm_test_users
            WHERE kind = 'anonymous' AND label = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (today_label,),
        )

        # 迁移兼容：允许前端仍传 refresh_token，但后端持久化为 SSOT。
        refresh_token = ((existing or {}).get("refresh_token") or "").strip()
        payload_refresh = (payload.refresh_token or "").strip()
        if payload_refresh and not refresh_token:
            refresh_token = payload_refresh

        if refresh_token and not payload.force_new:
            refresh_url = f"{supabase_url}/auth/v1/token?grant_type=refresh_token"
            resp = await client.post(refresh_url, headers=headers, json={"refresh_token": refresh_token})
            if resp.status_code == 200:
                data = resp.json()
                access_token = data.get("access_token") if isinstance(data, dict) else None
                if isinstance(access_token, str) and access_token:
                    new_refresh = data.get("refresh_token") if isinstance(data, dict) else refresh_token
                    # 当日复用：更新本地记录（不新增匿名用户）
                    if existing and existing.get("id"):
                        await db.execute(
                            """
                            UPDATE llm_test_users
                            SET refresh_token = ?, last_used_at = ?, last_refreshed_at = ?
                            WHERE id = ?
                            """,
                            (
                                str(new_refresh or refresh_token),
                                _utc_now_iso(),
                                _utc_now_iso(),
                                int(existing["id"]),
                            ),
                        )
                    else:
                        await db.execute(
                            """
                            INSERT INTO llm_test_users
                              (kind, label, username, supabase_user_id, refresh_token, meta_json, last_used_at, last_refreshed_at)
                            VALUES
                              ('anonymous', ?, 'anon', ?, ?, ?, ?, ?)
                            """,
                            (
                                today_label,
                                (existing or {}).get("supabase_user_id"),
                                str(new_refresh or refresh_token),
                                '{"note":"refreshed"}',
                                _utc_now_iso(),
                                _utc_now_iso(),
                            ),
                        )
                    return create_response(
                        data={
                            "mode": "anonymous",
                            "access_token": access_token,
                            "refresh_token": new_refresh if isinstance(new_refresh, str) else refresh_token,
                            "expires_in": data.get("expires_in") if isinstance(data, dict) else None,
                            "token_type": data.get("token_type") if isinstance(data, dict) else "bearer",
                            "note": "refreshed_today",
                        }
                    )

        signup_url = f"{supabase_url}/auth/v1/signup"
        resp = await client.post(signup_url, headers=headers, json={"options": {"anonymous": True}})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_anon_signup_failed",
                    message="supabase_anon_signup_failed",
                    request_id=request_id,
                    upstream_status=resp.status_code,
                ),
            )

        data = resp.json()
        access_token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=UPSTREAM_FAILED_STATUS,
                detail=create_response(
                    code=502,
                    msg="supabase_missing_access_token",
                    message="supabase_missing_access_token",
                    request_id=request_id,
                ),
            )

        created_refresh = data.get("refresh_token") if isinstance(data, dict) else None
        user_id = None
        if isinstance(data, dict):
            user = data.get("user")
            if isinstance(user, dict):
                user_id = user.get("id")

        # 持久化当日匿名用户：优先更新当日记录，避免无限创建。
        if existing and existing.get("id"):
            await db.execute(
                """
                UPDATE llm_test_users
                SET refresh_token = ?, supabase_user_id = ?, username = 'anon', last_used_at = ?, last_refreshed_at = NULL
                WHERE id = ?
                """,
                (
                    str(created_refresh or ""),
                    user_id,
                    _utc_now_iso(),
                    int(existing["id"]),
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO llm_test_users
                  (kind, label, username, supabase_user_id, refresh_token, meta_json, last_used_at)
                VALUES
                  ('anonymous', ?, 'anon', ?, ?, ?, ?)
                """,
                (
                    today_label,
                    user_id,
                    str(created_refresh or ""),
                    '{"note":"created"}',
                    _utc_now_iso(),
                ),
            )

        return create_response(
            data={
                "mode": "anonymous",
                "access_token": access_token,
                "refresh_token": created_refresh if isinstance(created_refresh, str) and created_refresh else None,
                "expires_in": data.get("expires_in") if isinstance(data, dict) else None,
                "token_type": data.get("token_type") if isinstance(data, dict) else "bearer",
                "user": data.get("user") if isinstance(data, dict) else None,
                "note": "created_today",
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
