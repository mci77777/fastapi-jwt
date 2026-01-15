"""Dashboard 本地账号与权限解析（SSOT：SQLite local_users + capability 映射）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status

from app.db import get_sqlite_manager

from .jwt_verifier import AuthenticatedUser

CAP_DASHBOARD_USERS_MANAGE = "dashboard_users_manage"
CAP_LLM_MANAGE = "llm_manage"
CAP_APP_USERS_MANAGE = "app_users_manage"
CAP_EXERCISE_MANAGE = "exercise_manage"


class DashboardRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    LLM_ADMIN = "llm_admin"
    APP_USER_ADMIN = "app_user_admin"
    EXERCISE_ADMIN = "exercise_admin"
    VIEWER = "viewer"


ROLE_CAPABILITIES: dict[DashboardRole, set[str]] = {
    DashboardRole.SUPER_ADMIN: {CAP_DASHBOARD_USERS_MANAGE, CAP_LLM_MANAGE, CAP_APP_USERS_MANAGE, CAP_EXERCISE_MANAGE},
    DashboardRole.LLM_ADMIN: {CAP_LLM_MANAGE},
    DashboardRole.APP_USER_ADMIN: {CAP_APP_USERS_MANAGE},
    DashboardRole.EXERCISE_ADMIN: {CAP_EXERCISE_MANAGE},
    DashboardRole.VIEWER: set(),
}

ALL_CAPABILITIES: set[str] = set().union(*ROLE_CAPABILITIES.values())


def normalize_dashboard_role(value: Any) -> DashboardRole:
    raw = str(value or "").strip().lower()
    for role in DashboardRole:
        if role.value == raw:
            return role
    return DashboardRole.VIEWER


def is_dashboard_admin_user(user: AuthenticatedUser) -> bool:
    """兼容历史：以 JWT claims 判定“管理员”。（仅用于非本地 token 的兜底判定）"""

    claims = getattr(user, "claims", {}) or {}
    if not isinstance(claims, dict):
        return False

    user_metadata = claims.get("user_metadata") or {}
    if isinstance(user_metadata, dict):
        username = str(user_metadata.get("username") or "").strip()
        if username == "admin" or bool(user_metadata.get("is_admin", False)):
            return True

    # 兼容：部分 Supabase/自定义 JWT 会把权限字段放在 app_metadata
    app_metadata = claims.get("app_metadata") or {}
    if isinstance(app_metadata, dict):
        role = str(app_metadata.get("role") or "").strip().lower()
        if role == "admin" or bool(app_metadata.get("is_admin", False)):
            return True

    role = str(claims.get("role") or "").strip().lower()
    return role == "admin"


def _is_local_dashboard_token(user: AuthenticatedUser) -> bool:
    claims = getattr(user, "claims", {}) or {}
    if not isinstance(claims, dict):
        return False
    app_metadata = claims.get("app_metadata") or {}
    if not isinstance(app_metadata, dict):
        return False
    return bool(app_metadata.get("dashboard_local", False))


def _extract_username_from_claims(user: AuthenticatedUser) -> str:
    claims = getattr(user, "claims", {}) or {}
    if not isinstance(claims, dict):
        return ""
    user_metadata = claims.get("user_metadata") or {}
    if not isinstance(user_metadata, dict):
        return ""
    return str(user_metadata.get("username") or "").strip()


@dataclass(slots=True)
class DashboardAccess:
    username: str
    role: DashboardRole
    is_active: bool
    is_superuser: bool
    capabilities: set[str]
    source: str  # local | claims


async def resolve_dashboard_access(request: Request, user: AuthenticatedUser) -> DashboardAccess:
    """解析 Dashboard 权限（本地账号以 SQLite 为准；否则走 claims 兜底）。"""

    username = _extract_username_from_claims(user)

    if _is_local_dashboard_token(user):
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": 401, "msg": "本地账号 token 缺少 username", "data": None},
            )

        db = get_sqlite_manager(request.app)
        row = await db.fetchone(
            "SELECT username, role, is_active FROM local_users WHERE username = ?",
            (username,),
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": 401, "msg": "账号不存在或已删除", "data": None},
            )

        raw_role = row.get("role")
        default_role = DashboardRole.SUPER_ADMIN.value if username == "admin" else DashboardRole.VIEWER.value
        role = normalize_dashboard_role(raw_role or default_role)
        is_active = int(row.get("is_active") if row.get("is_active") is not None else 1) == 1
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": 401, "msg": "账号已禁用", "data": None},
            )

        is_superuser = role == DashboardRole.SUPER_ADMIN
        capabilities = set(ALL_CAPABILITIES if is_superuser else ROLE_CAPABILITIES.get(role, set()))
        return DashboardAccess(
            username=username,
            role=role,
            is_active=is_active,
            is_superuser=is_superuser,
            capabilities=capabilities,
            source="local",
        )

    # 非本地 token：兼容旧 admin 判定；其余视作 viewer
    is_superuser = is_dashboard_admin_user(user)
    role = DashboardRole.SUPER_ADMIN if is_superuser else DashboardRole.VIEWER
    capabilities = set(ALL_CAPABILITIES if is_superuser else set())
    return DashboardAccess(
        username=username,
        role=role,
        is_active=True,
        is_superuser=is_superuser,
        capabilities=capabilities,
        source="claims",
    )


def has_capability(access: DashboardAccess, capability: str) -> bool:
    if not capability:
        return False
    return access.is_superuser or (capability in access.capabilities)
