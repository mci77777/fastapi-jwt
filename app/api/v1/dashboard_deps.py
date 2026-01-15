"""Dashboard 权限依赖（基于 SQLite local_users + capability SSOT）。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.api.v1.base import get_current_user_from_token
from app.auth import AuthenticatedUser
from app.auth.dashboard_access import DashboardAccess, DashboardRole, has_capability, resolve_dashboard_access
from app.core.middleware import get_current_request_id


def _detail(code: int, msg: str) -> dict:
    return {"code": int(code), "msg": str(msg), "data": None, "request_id": get_current_request_id() or ""}


async def get_dashboard_access(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
) -> DashboardAccess:
    return await resolve_dashboard_access(request, current_user)


def require_dashboard_capability(capability: str, *, msg: str = "无权限"):
    async def _dep(
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
    ) -> DashboardAccess:
        access = await resolve_dashboard_access(request, current_user)
        if has_capability(access, capability):
            return access
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_detail(403, msg))

    return _dep


def require_dashboard_capability_user(capability: str, *, msg: str = "无权限"):
    async def _dep(
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
    ) -> AuthenticatedUser:
        access = await resolve_dashboard_access(request, current_user)
        if has_capability(access, capability):
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_detail(403, msg))

    return _dep


async def require_dashboard_super_admin(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_from_token),  # noqa: B008
) -> DashboardAccess:
    access = await resolve_dashboard_access(request, current_user)
    if access.role == DashboardRole.SUPER_ADMIN:
        return access
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_detail(403, "需要超级管理员权限"))
