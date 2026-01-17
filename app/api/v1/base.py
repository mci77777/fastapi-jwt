"""基础认证端点（登录、用户信息等）。"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.auth.dashboard_access import (
    CAP_APP_USERS_MANAGE,
    CAP_DASHBOARD_USERS_MANAGE,
    CAP_EXERCISE_MANAGE,
    CAP_LLM_MANAGE,
    DashboardRole,
    has_capability,
    normalize_dashboard_role,
    resolve_dashboard_access,
)
from app.auth.local_password import hash_password, verify_password
from app.core.middleware import get_current_request_id
from app.db import get_sqlite_manager
from app.settings.config import get_settings

router = APIRouter(prefix="/base", tags=["base"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """登录请求模型。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应模型。"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class UserInfoResponse(BaseModel):
    """用户信息响应模型。"""

    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str | None = Field(None, description="邮箱")
    avatar: str | None = Field(None, description="头像")
    roles: list = Field(default_factory=list, description="角色列表")
    is_superuser: bool = Field(default=False, description="是否超级用户")
    is_active: bool = Field(default=True, description="是否激活")


def create_response(data: Any = None, code: int = 200, msg: str = "success") -> Dict[str, Any]:
    """创建统一的响应格式。"""
    payload: Dict[str, Any] = {"code": code, "data": data, "msg": msg}
    # 仅对“业务错误”（code!=200）补齐 request_id，便于排障与对账（SSOT：X-Request-Id）
    if code != 200:
        payload["request_id"] = get_current_request_id()
    return payload


class UpdatePasswordRequest(BaseModel):
    id: Optional[str] = Field(default=None, description="兼容字段：用户ID（本地改密不使用）")
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码")
    confirm_password: Optional[str] = Field(default=None, description="确认新密码（可选）")

def _default_role_for_username(username: str) -> str:
    return DashboardRole.ADMIN.value if str(username or "").strip() == "admin" else DashboardRole.USER.value


async def _get_or_seed_local_admin_password_hash(request: Request) -> str:
    db = get_sqlite_manager(request.app)
    row = await db.fetchone("SELECT password_hash, role, is_active FROM local_users WHERE username = ?", ("admin",))
    if row and row.get("password_hash"):
        # 兼容：历史行缺少 role/is_active 时自动补齐（SSOT：至少一个启用的 admin）。
        role = str(row.get("role") or "").strip().lower()
        is_active = row.get("is_active")
        need_fix = (not role) or (is_active is None)
        if need_fix:
            await db.execute(
                """
                UPDATE local_users
                SET role = COALESCE(NULLIF(role, ''), ?),
                    is_active = COALESCE(is_active, 1),
                    updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
                """,
                (DashboardRole.ADMIN.value, "admin"),
            )
        return str(row["password_hash"])

    # 首次启动：写入默认 admin/123456（可在 UI 里改密，持久化到 db.sqlite3）
    password_hash = hash_password("123456")
    await db.execute(
        """
        INSERT OR REPLACE INTO local_users(username, password_hash, role, is_active, updated_at)
        VALUES(?, ?, ?, 1, CURRENT_TIMESTAMP)
        """,
        ("admin", password_hash, DashboardRole.ADMIN.value),
    )
    return password_hash


def create_test_jwt_token(
    username: str,
    *,
    role: str | None = None,
    dashboard_local: bool = False,
    expire_hours: int = 24,
) -> str:
    """创建测试JWT token。

    Args:
        username: 用户名
        role: Dashboard 本地账号角色（可选；仅作为 debug/兼容字段，不作为 SSOT）
        dashboard_local: 是否为 Dashboard 本地账号 token（为 true 时，服务端会以 SQLite local_users 作为 SSOT）
        expire_hours: Token 有效期（小时），默认 24 小时

    Returns:
        JWT token 字符串
    """
    settings = get_settings()

    # 创建JWT payload
    now = int(time.time())
    # SSOT：issuer 仅认无尾随 "/" 的规范形态，避免与 JWTVerifier 的 allow-list（rstrip("/")）不一致导致 401 issuer_not_allowed
    issuer = (str(settings.supabase_issuer).rstrip("/") if settings.supabase_issuer else "http://localhost:9999")

    effective_role = str(role or _default_role_for_username(username)).strip().lower()
    is_admin = effective_role == DashboardRole.ADMIN.value

    app_metadata: dict[str, Any] = {"provider": "test", "providers": ["test"]}
    if dashboard_local:
        app_metadata["dashboard_local"] = True
        app_metadata["dashboard_role"] = effective_role

    payload = {
        "iss": issuer,
        "sub": f"test-user-{username}",
        "aud": "authenticated",
        "exp": now + (expire_hours * 3600),  # 默认 24 小时后过期
        "iat": now,
        "email": f"{username}@test.local",
        "role": "authenticated",
        "is_anonymous": False,
        "user_metadata": {"username": username, "is_admin": is_admin},
        "app_metadata": app_metadata,
    }

    # 使用Supabase JWT secret签名
    jwt_secret = settings.supabase_jwt_secret
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret is not configured")

    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    return token


async def get_current_user_from_token(
    request: Request,
    token: Optional[str] = Header(default=None, alias="token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """从token header或Authorization header中提取并验证用户。

    注意：此函数用于兼容前端的 token header。
    对于新的 API 端点，建议使用 app.auth.dependencies.get_current_user。
    """
    # 优先使用token header（前端使用）
    auth_token = token

    # 如果没有token header，尝试从Authorization header提取
    if not auth_token and authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
        else:
            auth_token = authorization

    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=create_response(code=401, msg="未提供认证令牌"))

    # 验证token - 使用 JWTVerifier
    from app.auth import get_jwt_verifier

    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(auth_token)
        request.state.user = user
        request.state.token = auth_token
        return user
    except HTTPException:
        # JWTVerifier 已经抛出了正确的 HTTPException
        raise
    except Exception as e:
        # 兜底错误处理
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=create_response(code=401, msg=f"令牌验证失败: {str(e)}")
        )


@router.get("/sse_probe", summary="SSE 流式探针（用于验证网关/代理未缓冲）")
async def sse_probe(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StreamingResponse:
    """返回一个短生命周期 SSE 流，用于验证端到端“真实流式”。

    语义：
    - 每秒发送 1 条 `event: probe`（共 8 条）
    - 末尾发送 `event: completed`
    - 若客户端/代理把这些事件合并成“一次性到达”，说明存在响应缓冲或压缩导致的流式失真。
    """

    request_id = getattr(request.state, "request_id", None) or get_current_request_id() or ""
    user_id = getattr(current_user, "uid", "") or ""

    async def gen():
        # 兼容部分反向代理的缓冲策略：先发送注释 padding，促使尽早 flush。
        yield ":" + (" " * 2048) + "\n\n"
        started_ms = int(time.time() * 1000)
        for seq in range(1, 9):
            ts_ms = int(time.time() * 1000)
            payload = {"ts": ts_ms, "seq": seq, "request_id": request_id, "user_id": user_id}
            logger.info("[SSE_PROBE_SENT] ts=%s request_id=%s seq=%s", ts_ms, request_id, seq)
            yield f"event: probe\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
            await asyncio.sleep(1.0)

        done_ts = int(time.time() * 1000)
        done = {"ts": done_ts, "seq": 9, "request_id": request_id, "user_id": user_id, "duration_ms": done_ts - started_ms}
        logger.info("[SSE_PROBE_COMPLETED] ts=%s request_id=%s duration_ms=%s", done_ts, request_id, done["duration_ms"])
        yield f"event: completed\ndata: {json.dumps(done, ensure_ascii=False, separators=(',', ':'))}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/access_token", summary="用户登录")
async def login(http_request: Request, request: LoginRequest) -> Dict[str, Any]:
    """
    用户名密码登录接口。

    **注意**: 当前版本使用Supabase JWT认证，此端点为兼容性端点。
    实际生产环境应该通过Supabase Auth进行认证。

    本地账号实现：
    - 使用 SQLite `local_users` 作为 Dashboard 本地账号 SSOT
    - 首次启动会自动 seed `admin/123456`（建议首次登录后立即改密）
    """
    username = (request.username or "").strip()
    password = (request.password or "").strip()

    if not username or not password:
        return create_response(code=400, msg="用户名或密码不能为空", data=None)

    db = get_sqlite_manager(http_request.app)

    if username == "admin":
        # 确保 admin 存在（首次启动自动 seed）
        await _get_or_seed_local_admin_password_hash(http_request)

    row = await db.fetchone(
        "SELECT username, password_hash, role, is_active FROM local_users WHERE username = ?",
        (username,),
    )
    if not row or not row.get("password_hash"):
        return create_response(code=401, msg="用户名或密码错误", data=None)

    is_active = int(row.get("is_active") if row.get("is_active") is not None else 1) == 1
    if not is_active:
        return create_response(code=403, msg="账号已禁用", data=None)

    if not verify_password(password, str(row["password_hash"])):
        return create_response(code=401, msg="用户名或密码错误", data=None)

    effective_role = normalize_dashboard_role(row.get("role") or _default_role_for_username(username)).value
    await db.execute(
        "UPDATE local_users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (username,),
    )

    test_token = create_test_jwt_token(username, role=effective_role, dashboard_local=True)
    return create_response(data={"access_token": test_token, "token_type": "bearer"})


@router.post("/refresh_token", summary="刷新 Token")
async def refresh_token(current_user: AuthenticatedUser = Depends(get_current_user_from_token)) -> Dict[str, Any]:
    """
    刷新 JWT Token。

    **功能**：
    - 验证当前 Token 是否有效
    - 生成新的 Token（延长有效期）
    - 返回新 Token 给前端

    **使用场景**：
    - Token 即将过期时自动刷新
    - 用户长时间使用系统时保持登录状态

    **注意**：
    - 需要携带有效的 Authorization header
    - 即使 Token 已过期但在宽限期内（时钟偏移容忍 ±120 秒）仍可刷新
    """
    # 从当前用户信息中提取用户名
    user_metadata = current_user.claims.get("user_metadata", {})
    username = user_metadata.get("username") or current_user.claims.get("email", "").split("@")[0]

    # 生成新的 Token（24 小时有效期）
    app_metadata = current_user.claims.get("app_metadata") or {}
    dashboard_local = bool(app_metadata.get("dashboard_local", False)) if isinstance(app_metadata, dict) else False
    dashboard_role = str(app_metadata.get("dashboard_role") or "").strip() if isinstance(app_metadata, dict) else ""
    new_token = create_test_jwt_token(username, role=(dashboard_role or None), dashboard_local=dashboard_local)

    return create_response(
        data={
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 小时（秒）
        },
        msg="Token 刷新成功",
    )


@router.get("/userinfo", summary="获取用户信息")
async def get_user_info(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),
) -> Dict[str, Any]:
    """获取当前登录用户的信息。"""
    try:
        access = await resolve_dashboard_access(request, current_user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and isinstance(getattr(exc, "detail", None), dict):
            return create_response(code=401, msg=str(exc.detail.get("msg") or "登录已过期"), data=None)
        return create_response(code=401, msg="登录已过期", data=None)

    user_metadata = current_user.claims.get("user_metadata", {}) or {}
    display_username = user_metadata.get("username") or current_user.claims.get("email", current_user.uid)

    return create_response(
        data={
            "id": current_user.uid,
            "username": display_username,
            "email": current_user.claims.get("email"),
            "avatar": user_metadata.get("avatar_url"),
            "roles": [access.role.value],
            "is_superuser": bool(access.is_superuser),
            "is_active": bool(access.is_active),
        }
    )


@router.get("/usermenu", summary="获取用户菜单")
async def get_user_menu(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),
) -> Dict[str, Any]:
    """获取当前用户的菜单权限。"""
    try:
        access = await resolve_dashboard_access(request, current_user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and isinstance(getattr(exc, "detail", None), dict):
            return create_response(code=401, msg=str(exc.detail.get("msg") or "登录已过期"), data=None)
        return create_response(code=401, msg="登录已过期", data=None)

    # 临时硬编码菜单，实际应该从数据库查询
    # 菜单配置：Dashboard (0) → 系统管理 (5) → AI模型管理 (10)
    menus = [
        {
            "name": "Dashboard",
            "path": "/dashboard",
            "component": "/dashboard",
            "icon": "mdi:view-dashboard-outline",
            "order": 0,
            "is_hidden": False,
            "redirect": None,  # 修复：不设置 redirect，让前端自动跳转到第一个子路由
            "keepalive": False,
            "children": [
                {
                    "name": "概览",
                    "path": "",  # 修复：使用空路径作为默认子路由
                    "component": "/dashboard",
                    "icon": "mdi:chart-box-outline",
                    "order": 1,
                    "is_hidden": True,  # 修复：隐藏默认子路由，避免在菜单中重复显示
                    "keepalive": False,
                },
                {
                    "name": "API 监控",
                    "path": "api-monitor",
                    "component": "/dashboard/ApiMonitor",
                    "icon": "mdi:api",
                    "order": 2,
                    "is_hidden": False,
                    "keepalive": False,
                },
            ],
        },
    ]

    system_children: list[dict[str, Any]] = []
    if has_capability(access, CAP_LLM_MANAGE):
        system_children.extend(
            [
                {
                    "name": "AI 供应商",
                    "path": "ai",
                    "component": "/system/ai",
                    "icon": "carbon:ai-status",
                    "order": 1,
                    "is_hidden": False,
                    "keepalive": False,
                },
                {
                    "name": "Prompt 管理",
                    "path": "ai/prompt",
                    "component": "/system/ai/prompt",
                    "icon": "carbon:prompt-template",
                    "order": 2,
                    "is_hidden": False,
                    "keepalive": False,
                },
            ]
        )

    if has_capability(access, CAP_APP_USERS_MANAGE):
        system_children.extend(
            [
                {
                    "name": "App 用户管理",
                    "path": "app-users",
                    "component": "/system/app-users",
                    "icon": "mdi:account-multiple-outline",
                    "order": 3,
                    "is_hidden": False,
                    "keepalive": False,
                },
                {
                    "name": "用户管理配置",
                    "path": "app-users/config",
                    "component": "/system/app-users/config",
                    "icon": "mdi:cog-outline",
                    "order": 4,
                    "is_hidden": False,
                    "keepalive": False,
                },
                {
                    "name": "订阅等级配置",
                    "path": "user-entitlements/config",
                    "component": "/system/user-entitlements/config",
                    "icon": "mdi:tune-variant",
                    "order": 5,
                    "is_hidden": False,
                    "keepalive": False,
                },
            ]
        )

    if has_capability(access, CAP_DASHBOARD_USERS_MANAGE):
        system_children.append(
            {
                "name": "后台账号",
                "path": "admin-accounts",
                "component": "/system/admin-accounts",
                "icon": "mdi:account-key-outline",
                "order": 6,
                "is_hidden": False,
                "keepalive": False,
            }
        )

    if system_children:
        menus.append(
            {
                "name": "系统管理",
                "path": "/system",
                "component": "/system",
                "icon": "carbon:settings-adjust",
                "order": 5,
                "is_hidden": False,
                "redirect": None,
                "keepalive": False,
                "children": system_children,
            }
        )

    if has_capability(access, CAP_LLM_MANAGE):
        menus.append(
            {
                "name": "AI模型管理",
                "path": "/ai",
                "component": "/ai",
                "icon": "mdi:robot-outline",
                "order": 10,
                "is_hidden": False,
                "redirect": None,
                "keepalive": False,
                "children": [
                    {
                        "name": "模型映射",
                        "path": "",
                        "alias": ["/ai/mapping", "/ai/catalog"],
                        "component": "/ai/model-suite/mapping",
                        "icon": "mdi:graph-outline",
                        "order": 1,
                        "is_hidden": False,
                        "keepalive": False,
                    },
                    {
                        "name": "JWT 测试",
                        "path": "jwt",
                        "component": "/ai/model-suite/jwt",
                        "icon": "mdi:chat-processing-outline",
                        "order": 2,
                        "is_hidden": False,
                        "keepalive": False,
                    },
                    {
                        "name": "E2E 记录",
                        "path": "e2e-records",
                        "component": "/ai/model-suite/e2e-records",
                        "icon": "mdi:clipboard-text-clock-outline",
                        "order": 3,
                        "is_hidden": False,
                        "keepalive": False,
                    },
                ],
            }
        )

    if has_capability(access, CAP_EXERCISE_MANAGE):
        menus.append(
            {
                "name": "动作库管理",
                "path": "/exercise",
                "component": "/exercise",
                "icon": "mdi:dumbbell",
                "order": 11,
                "is_hidden": False,
                "redirect": None,
                "keepalive": False,
                "children": [
                    {
                        "name": "官方库种子发布",
                        "path": "library/seed",
                        "component": "/exercise/library/seed",
                        "icon": "mdi:database-arrow-up",
                        "order": 1,
                        "is_hidden": False,
                        "keepalive": False,
                    }
                ],
            }
        )
    return create_response(data=menus)


@router.get("/userapi", summary="获取用户API权限")
async def get_user_api(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),
) -> Dict[str, Any]:
    """获取当前用户的API权限。"""
    try:
        access = await resolve_dashboard_access(request, current_user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and isinstance(getattr(exc, "detail", None), dict):
            return create_response(code=401, msg=str(exc.detail.get("msg") or "登录已过期"), data=None)
        return create_response(code=401, msg="登录已过期", data=None)

    # KISS：前端仅用该列表做“按钮/入口级”权限判断；服务端仍以 require_llm_admin 为最终裁决。
    apis: list[str] = [
        # App/普通用户只需要读取映射后的白名单（view=mapped 为默认且安全）。
        "get/api/v1/llm/models",
    ]

    if has_capability(access, CAP_LLM_MANAGE):
        apis.extend(
            [
                # 供应商 endpoints（admin）
                "post/api/v1/llm/models",
                "put/api/v1/llm/models",
                "delete/api/v1/llm/models",
                "post/api/v1/llm/models/check-all",
                "post/api/v1/llm/models/check",
                "post/api/v1/llm/models/sync",
                "post/api/v1/llm/models/sync-one",
                "get/api/v1/llm/models/blocked",
                "put/api/v1/llm/models/blocked",
                # 映射（admin）
                "get/api/v1/llm/model-groups",
                "post/api/v1/llm/model-groups",
                "post/api/v1/llm/model-groups/activate",
                "delete/api/v1/llm/model-groups",
                # Prompt（admin）
                "get/api/v1/llm/prompts",
                "post/api/v1/llm/prompts",
                "put/api/v1/llm/prompts",
                "delete/api/v1/llm/prompts",
                "post/api/v1/llm/prompts/activate",
                "post/api/v1/llm/prompts/test",
                # JWT 真实测试（admin）
                "post/api/v1/llm/tests/create-mail-user",
                "get/api/v1/llm/tests/mail-users",
                "post/api/v1/llm/tests/mail-users/refresh",
                "post/api/v1/llm/tests/anon-token",
            ]
        )

    if has_capability(access, CAP_EXERCISE_MANAGE):
        apis.extend(
            [
                # 动作库发布（admin）
                "post/api/v1/admin/exercise/library/publish",
                "post/api/v1/admin/exercise/library/patch",
            ]
        )

    if has_capability(access, CAP_APP_USERS_MANAGE):
        apis.extend(
            [
                # 订阅等级配置（admin）
                "get/api/v1/admin/user-entitlements/presets",
                "post/api/v1/admin/user-entitlements/presets",
                "delete/api/v1/admin/user-entitlements/presets",
                # App 用户管理（admin）
                "get/api/v1/admin/app-users/config",
                "post/api/v1/admin/app-users/config",
                "get/api/v1/admin/app-users/bootstrap",
                "get/api/v1/admin/app-users/stats",
                "get/api/v1/admin/app-users/list",
                "get/api/v1/admin/app-users",
                "post/api/v1/admin/app-users/entitlements",
                "post/api/v1/admin/app-users/permissions",
                "post/api/v1/admin/app-users/disable",
                "post/api/v1/admin/app-users/enable",
                "post/api/v1/admin/app-users/reset-password",
            ]
        )

    if has_capability(access, CAP_DASHBOARD_USERS_MANAGE):
        apis.extend(
            [
                "get/api/v1/admin/dashboard-users/list",
                "post/api/v1/admin/dashboard-users/create",
                "post/api/v1/admin/dashboard-users/role",
                "post/api/v1/admin/dashboard-users/enable",
                "post/api/v1/admin/dashboard-users/disable",
                "post/api/v1/admin/dashboard-users/reset-password",
            ]
        )

    # 去重保持顺序
    apis = list(dict.fromkeys(apis))
    return create_response(data=apis)


@router.post("/update_password", summary="更新密码")
async def update_password(
    http_request: Request,
    payload: UpdatePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),
) -> Dict[str, Any]:
    """更新当前用户密码。

    说明：仅支持本地 Dashboard 账号改密（不影响 Supabase 用户）。
    """
    try:
        access = await resolve_dashboard_access(http_request, current_user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and isinstance(getattr(exc, "detail", None), dict):
            return create_response(code=401, msg=str(exc.detail.get("msg") or "登录已过期"), data=None)
        return create_response(code=401, msg="登录已过期", data=None)

    if access.source != "local":
        return create_response(code=403, msg="仅支持本地账号修改密码", data=None)

    old_password = (payload.old_password or "").strip()
    new_password = (payload.new_password or "").strip()
    if not old_password or not new_password:
        return create_response(code=400, msg="密码不能为空", data=None)
    if payload.confirm_password is not None and new_password != (payload.confirm_password or "").strip():
        return create_response(code=400, msg="两次输入的新密码不一致", data=None)
    if len(new_password) < 6:
        return create_response(code=400, msg="新密码长度至少 6 位", data=None)

    db = get_sqlite_manager(http_request.app)
    row = await db.fetchone("SELECT password_hash FROM local_users WHERE username = ?", (access.username,))
    if not row or not row.get("password_hash"):
        return create_response(code=401, msg="账号不存在或已删除", data=None)

    if not verify_password(old_password, str(row["password_hash"])):
        return create_response(code=401, msg="旧密码不正确", data=None)

    await db.execute(
        "UPDATE local_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (hash_password(new_password), access.username),
    )
    return create_response(code=200, msg="密码更新成功", data={"username": access.username})
