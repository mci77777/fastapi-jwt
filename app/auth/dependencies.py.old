"""认证相关的 FastAPI 依赖声明。"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import Header, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from app.auth.jwt_verifier import AuthenticatedUser, get_jwt_verifier

logger = logging.getLogger(__name__)


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
    request.state.user_type = user.user_type  # 设置用户类型到请求上下文

    # 记录用户活跃度（Phase 1）
    await _record_user_activity(request, user)

    return user


async def _record_user_activity(request: Request, user: AuthenticatedUser) -> None:
    """记录用户活跃度到 user_activity_stats 表。

    Args:
        request: FastAPI 请求对象
        user: 已认证用户
    """
    try:
        from app.db.sqlite_manager import get_sqlite_manager

        db = get_sqlite_manager(request.app)
        today = datetime.now().date().isoformat()

        await db.execute(
            """
            INSERT INTO user_activity_stats (user_id, user_type, activity_date, request_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, activity_date)
            DO UPDATE SET
                request_count = request_count + 1,
                last_request_at = CURRENT_TIMESTAMP
        """,
            [user.uid, user.user_type, today],
        )
    except Exception as exc:
        # 不阻塞主流程，仅记录日志
        logger.warning("Failed to record user activity: %s", exc)


async def get_authenticated_user_optional(request: Request) -> Optional[AuthenticatedUser]:
    """从请求状态中获取已认证的用户（如果存在）。"""
    return getattr(request.state, 'user', None)
