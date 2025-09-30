"""基础认证端点（登录、用户信息等）。"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, Field
import jwt
import time

from app.auth import AuthenticatedUser
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
    return {
        "code": code,
        "data": data,
        "msg": msg
    }


def create_test_jwt_token(username: str) -> str:
    """创建测试JWT token。"""
    settings = get_settings()

    # 创建JWT payload
    now = int(time.time())
    issuer = str(settings.supabase_issuer) if settings.supabase_issuer else "http://localhost:9999"

    payload = {
        "iss": issuer,
        "sub": f"test-user-{username}",
        "aud": "authenticated",
        "exp": now + 3600,  # 1小时后过期
        "iat": now,
        "email": f"{username}@test.local",
        "role": "authenticated",
        "is_anonymous": False,
        "user_metadata": {
            "username": username,
            "is_admin": username == "admin"
        },
        "app_metadata": {
            "provider": "test",
            "providers": ["test"]
        }
    }

    # 使用Supabase JWT secret签名
    token = jwt.encode(
        payload,
        settings.supabase_jwt_secret,
        algorithm="HS256"
    )

    return token


async def get_current_user_from_token(
    request: Request,
    token: Optional[str] = Header(default=None, alias="token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """从token header或Authorization header中提取并验证用户。"""
    # 优先使用token header（前端使用）
    auth_token = token

    # 如果没有token header，尝试从Authorization header提取
    if not auth_token and authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
        else:
            auth_token = authorization

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_response(code=401, msg="未提供认证令牌")
        )

    # 验证token
    settings = get_settings()
    try:
        payload = jwt.decode(
            auth_token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True}
        )

        user = AuthenticatedUser(
            uid=payload.get("sub"),
            claims=payload,
            user_type="anonymous" if payload.get("is_anonymous") else "permanent"
        )
        request.state.user = user
        request.state.token = auth_token
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_response(code=401, msg="令牌已过期")
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_response(code=401, msg=f"无效的令牌: {str(e)}")
        )


@router.post("/access_token", summary="用户登录")
async def login(request: LoginRequest) -> Dict[str, Any]:
    """
    用户名密码登录接口。

    **注意**: 当前版本使用Supabase JWT认证，此端点为兼容性端点。
    实际生产环境应该通过Supabase Auth进行认证。

    临时实现：
    - admin/123456 返回测试JWT token
    - 其他用户名密码返回401
    """
    # 临时硬编码的测试账号
    if request.username == "admin" and request.password == "123456":
        # 创建真实的JWT token
        test_token = create_test_jwt_token(request.username)

        return create_response(data={
            "access_token": test_token,
            "token_type": "bearer"
        })

    # 认证失败
    return create_response(
        code=401,
        msg="用户名或密码错误",
        data=None
    )


@router.get("/userinfo", summary="获取用户信息")
async def get_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token)
) -> Dict[str, Any]:
    """获取当前登录用户的信息。"""
    user_metadata = current_user.claims.get("user_metadata", {})

    return create_response(data={
        "id": current_user.uid,
        "username": user_metadata.get("username") or current_user.claims.get("email", current_user.uid),
        "email": current_user.claims.get("email"),
        "avatar": user_metadata.get("avatar_url"),
        "roles": ["admin"] if user_metadata.get("is_admin") else ["user"],
        "is_superuser": user_metadata.get("is_admin", False),
        "is_active": True
    })


@router.get("/usermenu", summary="获取用户菜单")
async def get_user_menu(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token)
) -> Dict[str, Any]:
    """获取当前用户的菜单权限。"""
    # 临时返回空菜单，实际应该从数据库查询
    return create_response(data=[])


@router.get("/userapi", summary="获取用户API权限")
async def get_user_api(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token)
) -> Dict[str, Any]:
    """获取当前用户的API权限。"""
    # 临时返回空权限，实际应该从数据库查询
    return create_response(data=[])


@router.post("/update_password", summary="更新密码")
async def update_password(
    current_user: AuthenticatedUser = Depends(get_current_user_from_token)
) -> Dict[str, Any]:
    """更新当前用户密码。"""
    # 临时实现，实际应该调用Supabase Auth API
    return create_response(
        code=501,
        msg="密码更新功能暂未实现，请通过Supabase Auth进行密码管理",
        data=None
    )

