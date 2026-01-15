"""Admin: manage Dashboard local accounts (SSOT: SQLite local_users)."""

from __future__ import annotations

import secrets
import string
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.base import create_response
from app.api.v1.dashboard_deps import require_dashboard_super_admin
from app.auth.dashboard_access import DashboardRole, normalize_dashboard_role
from app.auth.local_password import hash_password
from app.db import get_sqlite_manager

router = APIRouter(prefix="/admin/dashboard-users", tags=["dashboard-users-admin"])


def _default_role_for_username(username: str) -> DashboardRole:
    return DashboardRole.ADMIN if str(username or "").strip() == "admin" else DashboardRole.USER


def _random_password(length: int = 16) -> str:
    safe_len = max(int(length), 8)
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(safe_len))


_ALLOWED_ROLE_INPUTS: set[str] = {
    # 新三档
    "admin",
    "manager",
    "user",
    # 兼容历史四档/五档（会折叠到新三档）
    "super_admin",
    "llm_admin",
    "app_user_admin",
    "exercise_admin",
    "viewer",
}


def _is_valid_role_input(value: Any) -> bool:
    raw = str(value or "").strip().lower()
    return raw in _ALLOWED_ROLE_INPUTS


async def _count_other_active_admins(db, *, exclude_username: str) -> int:
    row = await db.fetchone(
        """
        SELECT COUNT(1) as total
        FROM local_users
        WHERE username <> ?
          AND is_active = 1
          AND LOWER(COALESCE(role, '')) IN (?, ?)
        """,
        (exclude_username, DashboardRole.ADMIN.value, "super_admin"),
    )
    return int((row or {}).get("total") or 0)


async def _ensure_not_removing_last_super_admin(
    db,
    *,
    target_username: str,
    next_role: DashboardRole | None = None,
    next_is_active: bool | None = None,
) -> bool:
    """保护：至少保留一个 active admin。"""

    current = await db.fetchone(
        "SELECT username, role, is_active FROM local_users WHERE username = ?",
        (target_username,),
    )
    if not current:
        return True

    current_role = normalize_dashboard_role(current.get("role") or _default_role_for_username(target_username).value)
    current_active = int(current.get("is_active") if current.get("is_active") is not None else 1) == 1

    if current_role != DashboardRole.ADMIN or not current_active:
        return True

    final_role = next_role or current_role
    final_active = current_active if next_is_active is None else bool(next_is_active)
    if final_role == DashboardRole.ADMIN and final_active:
        return True

    return (await _count_other_active_admins(db, exclude_username=target_username)) > 0


class DashboardUserItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    role: str
    is_active: bool
    last_login_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CreateDashboardUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default=DashboardRole.USER.value)
    is_active: bool = Field(default=True)


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., min_length=1)
    confirm_username: str = Field(..., min_length=1, description="二次确认：必须与 path username 相同")


class ToggleActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_username: str = Field(..., min_length=1, description="二次确认：必须与 path username 相同")


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_username: str = Field(..., min_length=1, description="二次确认：必须与 path username 相同")
    password_length: int = Field(default=16, ge=8, le=64)


@router.get("/list")
async def list_dashboard_users(
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    db = get_sqlite_manager(request.app)
    rows = await db.fetchall(
        """
        SELECT username, role, is_active, last_login_at, created_at, updated_at
        FROM local_users
        ORDER BY username ASC
        """,
        (),
    )

    items: list[dict[str, Any]] = []
    for row in rows:
        username = str(row.get("username") or "").strip()
        role = normalize_dashboard_role(row.get("role") or _default_role_for_username(username).value).value
        is_active = int(row.get("is_active") if row.get("is_active") is not None else 1) == 1
        items.append(
            DashboardUserItem(
                username=username,
                role=role,
                is_active=is_active,
                last_login_at=row.get("last_login_at"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            ).model_dump(mode="json")
        )
    return create_response(data=items)


@router.post("/create")
async def create_dashboard_user(
    payload: CreateDashboardUserRequest,
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    username = str(payload.username or "").strip()
    if not username:
        return create_response(code=400, msg="用户名不能为空", data=None)

    if not _is_valid_role_input(payload.role):
        return create_response(code=400, msg="不支持的角色", data=None)

    role = normalize_dashboard_role(payload.role)

    db = get_sqlite_manager(request.app)
    existing = await db.fetchone("SELECT username FROM local_users WHERE username = ?", (username,))
    if existing:
        return create_response(code=409, msg="用户名已存在", data=None)

    await db.execute(
        """
        INSERT INTO local_users(username, password_hash, role, is_active, created_at, updated_at)
        VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (username, hash_password(payload.password), role.value, 1 if payload.is_active else 0),
    )
    return create_response(code=200, msg="创建成功", data={"username": username, "role": role.value, "is_active": bool(payload.is_active)})


@router.post("/{username}/role")
async def update_dashboard_user_role(
    username: str,
    payload: UpdateRoleRequest,
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    target = str(username or "").strip()
    if not target:
        return create_response(code=400, msg="用户名不能为空", data=None)
    if str(payload.confirm_username or "").strip() != target:
        return create_response(code=400, msg="二次确认失败：confirm_username 不匹配", data=None)

    if not _is_valid_role_input(payload.role):
        return create_response(code=400, msg="不支持的角色", data=None)

    role = normalize_dashboard_role(payload.role)

    db = get_sqlite_manager(request.app)
    exists = await db.fetchone("SELECT username FROM local_users WHERE username = ?", (target,))
    if not exists:
        return create_response(code=404, msg="账号不存在", data=None)

    ok = await _ensure_not_removing_last_super_admin(db, target_username=target, next_role=role)
    if not ok:
        return create_response(code=400, msg="禁止降级：至少保留一个启用的 admin", data=None)

    await db.execute(
        "UPDATE local_users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (role.value, target),
    )
    return create_response(code=200, msg="已更新角色", data={"username": target, "role": role.value})


@router.post("/{username}/disable")
async def disable_dashboard_user(
    username: str,
    payload: ToggleActiveRequest,
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    target = str(username or "").strip()
    if not target:
        return create_response(code=400, msg="用户名不能为空", data=None)
    if str(payload.confirm_username or "").strip() != target:
        return create_response(code=400, msg="二次确认失败：confirm_username 不匹配", data=None)

    db = get_sqlite_manager(request.app)
    exists = await db.fetchone("SELECT username FROM local_users WHERE username = ?", (target,))
    if not exists:
        return create_response(code=404, msg="账号不存在", data=None)

    ok = await _ensure_not_removing_last_super_admin(db, target_username=target, next_is_active=False)
    if not ok:
        return create_response(code=400, msg="禁止禁用：至少保留一个启用的 admin", data=None)

    await db.execute(
        "UPDATE local_users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (target,),
    )
    return create_response(code=200, msg="已禁用账号", data={"username": target, "is_active": False})


@router.post("/{username}/enable")
async def enable_dashboard_user(
    username: str,
    payload: ToggleActiveRequest,
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    target = str(username or "").strip()
    if not target:
        return create_response(code=400, msg="用户名不能为空", data=None)
    if str(payload.confirm_username or "").strip() != target:
        return create_response(code=400, msg="二次确认失败：confirm_username 不匹配", data=None)

    db = get_sqlite_manager(request.app)
    exists = await db.fetchone("SELECT username FROM local_users WHERE username = ?", (target,))
    if not exists:
        return create_response(code=404, msg="账号不存在", data=None)

    await db.execute(
        "UPDATE local_users SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (target,),
    )
    return create_response(code=200, msg="已启用账号", data={"username": target, "is_active": True})


@router.post("/{username}/reset-password")
async def reset_dashboard_user_password(
    username: str,
    payload: ResetPasswordRequest,
    request: Request,
    _: Any = Depends(require_dashboard_super_admin),  # noqa: B008
) -> dict[str, Any]:
    target = str(username or "").strip()
    if not target:
        return create_response(code=400, msg="用户名不能为空", data=None)
    if str(payload.confirm_username or "").strip() != target:
        return create_response(code=400, msg="二次确认失败：confirm_username 不匹配", data=None)

    db = get_sqlite_manager(request.app)
    exists = await db.fetchone("SELECT username FROM local_users WHERE username = ?", (target,))
    if not exists:
        return create_response(code=404, msg="账号不存在", data=None)

    new_password = _random_password(int(payload.password_length))
    await db.execute(
        "UPDATE local_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
        (hash_password(new_password), target),
    )
    return create_response(
        code=200,
        msg="密码已重置（仅本次返回明文，请立即复制保存）",
        data={"username": target, "password": new_password},
    )
