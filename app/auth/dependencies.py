"""认证相关的 FastAPI 依赖声明。"""
from typing import Optional

from fastapi import Header, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from app.auth.jwt_verifier import AuthenticatedUser, get_jwt_verifier


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthorized", "message": message},
    )


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _unauthorized("Authorization header missing")

    scheme, param = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not param:
        raise _unauthorized("Authorization header must be 'Bearer <token>'")
    return param


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """解析并验证当前请求的 Bearer Token。"""

    token = _extract_bearer_token(authorization)
    verifier = get_jwt_verifier()
    user = verifier.verify_token(token)
    request.state.user = user
    request.state.token = token
    return user
