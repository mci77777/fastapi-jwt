"""基础认证端点（登录、用户信息等）。"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser
from app.core.middleware import get_current_request_id
from app.db import get_sqlite_manager
from app.settings.config import get_settings

router = APIRouter(prefix="/base", tags=["base"])


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


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * ((4 - (len(text) % 4)) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _hash_password(password: str) -> str:
    # KISS：使用 stdlib scrypt（无需额外依赖），仅用于本地 admin 账号存储。
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(key)}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, key_b64 = stored.split("$", 5)
        if algo != "scrypt":
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(key_b64)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


async def _get_or_seed_local_admin_password_hash(request: Request) -> str:
    db = get_sqlite_manager(request.app)
    row = await db.fetchone("SELECT password_hash FROM local_users WHERE username = ?", ("admin",))
    if row and row.get("password_hash"):
        return str(row["password_hash"])

    # 首次启动：写入默认 admin/123456（可在 UI 里改密，持久化到 db.sqlite3）
    password_hash = _hash_password("123456")
    await db.execute(
        "INSERT OR REPLACE INTO local_users(username, password_hash, updated_at) VALUES(?, ?, CURRENT_TIMESTAMP)",
        ("admin", password_hash),
    )
    return password_hash


def create_test_jwt_token(username: str, expire_hours: int = 24) -> str:
    """创建测试JWT token。

    Args:
        username: 用户名
        expire_hours: Token 有效期（小时），默认 24 小时

    Returns:
        JWT token 字符串
    """
    settings = get_settings()

    # 创建JWT payload
    now = int(time.time())
    # SSOT：issuer 仅认无尾随 "/" 的规范形态，避免与 JWTVerifier 的 allow-list（rstrip("/")）不一致导致 401 issuer_not_allowed
    issuer = (str(settings.supabase_issuer).rstrip("/") if settings.supabase_issuer else "http://localhost:9999")

    payload = {
        "iss": issuer,
        "sub": f"test-user-{username}",
        "aud": "authenticated",
        "exp": now + (expire_hours * 3600),  # 默认 24 小时后过期
        "iat": now,
        "email": f"{username}@test.local",
        "role": "authenticated",
        "is_anonymous": False,
        "user_metadata": {"username": username, "is_admin": username == "admin"},
        "app_metadata": {"provider": "test", "providers": ["test"]},
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


@router.post("/access_token", summary="用户登录")
async def login(http_request: Request, request: LoginRequest) -> Dict[str, Any]:
    """
    用户名密码登录接口。

    **注意**: 当前版本使用Supabase JWT认证，此端点为兼容性端点。
    实际生产环境应该通过Supabase Auth进行认证。

    临时实现：
    - admin/123456 返回测试JWT token
    - 其他用户名密码返回401
    """
    username = (request.username or "").strip()
    password = (request.password or "").strip()

    # Dashboard 本地账号：仅允许 admin（SSOT），密码可通过 /base/update_password 持久化更新。
    if username == "admin":
        password_hash = await _get_or_seed_local_admin_password_hash(http_request)
        if _verify_password(password, password_hash):
            test_token = create_test_jwt_token(username)
            return create_response(data={"access_token": test_token, "token_type": "bearer"})
        return create_response(code=401, msg="用户名或密码错误", data=None)

    # 认证失败
    return create_response(code=401, msg="用户名或密码错误", data=None)


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
    new_token = create_test_jwt_token(username)

    return create_response(
        data={
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 小时（秒）
        },
        msg="Token 刷新成功",
    )


@router.get("/userinfo", summary="获取用户信息")
async def get_user_info(current_user: AuthenticatedUser = Depends(get_current_user_from_token)) -> Dict[str, Any]:
    """获取当前登录用户的信息。"""
    user_metadata = current_user.claims.get("user_metadata", {})

    return create_response(
        data={
            "id": current_user.uid,
            "username": user_metadata.get("username") or current_user.claims.get("email", current_user.uid),
            "email": current_user.claims.get("email"),
            "avatar": user_metadata.get("avatar_url"),
            "roles": ["admin"] if user_metadata.get("is_admin") else ["user"],
            "is_superuser": user_metadata.get("is_admin", False),
            "is_active": True,
        }
    )


@router.get("/usermenu", summary="获取用户菜单")
async def get_user_menu(current_user: AuthenticatedUser = Depends(get_current_user_from_token)) -> Dict[str, Any]:
    """获取当前用户的菜单权限。"""
    print("=" * 80)
    print("GET /usermenu called - NEW VERSION")
    print("=" * 80)
    import logging

    logger = logging.getLogger(__name__)
    logger.info("=== get_user_menu called === v3")

    user_metadata = current_user.claims.get("user_metadata") or {}
    username = (user_metadata.get("username") or "").strip()
    is_admin = bool(user_metadata.get("is_admin", False)) or username == "admin"

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
        {
            "name": "系统管理",
            "path": "/system",
            "component": "/system",
            "icon": "carbon:settings-adjust",
            "order": 5,
            "is_hidden": False,
            "redirect": None,
            "keepalive": False,
            "children": [
                {
                    "name": "AI 配置",
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
            ],
        },
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
                    "name": "JWT测试",
                    "path": "jwt",
                    "component": "/ai/model-suite/jwt",
                    "icon": "mdi:chat-processing-outline",
                    "order": 2,
                    "is_hidden": False,
                    "keepalive": False,
                },
            ],
        },
    ]

    if is_admin:
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
    logger.info(f"Returning menus: {menus}")
    return create_response(data=menus)


@router.get("/userapi", summary="获取用户API权限")
async def get_user_api(current_user: AuthenticatedUser = Depends(get_current_user_from_token)) -> Dict[str, Any]:
    """获取当前用户的API权限。"""
    user_metadata = current_user.claims.get("user_metadata") or {}
    username = (user_metadata.get("username") or "").strip()
    is_admin = bool(user_metadata.get("is_admin", False)) or username == "admin"

    # 临时硬编码API权限，实际应该从数据库查询
    apis = [
        "get/api/v1/llm/models",
        "post/api/v1/llm/models",
        "put/api/v1/llm/models",
        "get/api/v1/llm/prompts",
        "post/api/v1/llm/prompts",
        "put/api/v1/llm/prompts",
        "post/api/v1/llm/prompts/activate",
    ]

    if is_admin:
        apis.append("post/api/v1/admin/exercise/library/publish")
        apis.append("post/api/v1/admin/exercise/library/patch")
        apis.append("get/api/v1/llm/models/blocked")
        apis.append("put/api/v1/llm/models/blocked")
        apis.append("post/api/v1/llm/model-groups")
        apis.append("post/api/v1/llm/model-groups/activate")
        apis.append("post/api/v1/llm/model-groups/sync-to-supabase")
    return create_response(data=apis)


@router.post("/update_password", summary="更新密码")
async def update_password(
    http_request: Request,
    payload: UpdatePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),
) -> Dict[str, Any]:
    """更新当前用户密码。

    说明：仅支持本地 Dashboard 账号 admin 的改密（不影响 Supabase 用户）。
    """
    user_metadata = current_user.claims.get("user_metadata") or {}
    username = (user_metadata.get("username") or "").strip()
    is_admin = bool(user_metadata.get("is_admin", False)) or username == "admin"
    if not is_admin:
        return create_response(code=403, msg="无权限修改密码", data=None)

    old_password = (payload.old_password or "").strip()
    new_password = (payload.new_password or "").strip()
    if not old_password or not new_password:
        return create_response(code=400, msg="密码不能为空", data=None)
    if payload.confirm_password is not None and new_password != (payload.confirm_password or "").strip():
        return create_response(code=400, msg="两次输入的新密码不一致", data=None)
    if len(new_password) < 6:
        return create_response(code=400, msg="新密码长度至少 6 位", data=None)

    password_hash = await _get_or_seed_local_admin_password_hash(http_request)
    if not _verify_password(old_password, password_hash):
        return create_response(code=401, msg="旧密码不正确", data=None)

    db = get_sqlite_manager(http_request.app)
    await db.execute(
        "UPDATE local_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (_hash_password(new_password), "admin"),
    )
    return create_response(code=200, msg="密码更新成功", data={"username": "admin"})
