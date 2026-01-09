"""Supabase Auth Admin client (service role) for managing auth.users via GoTrue Admin API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.settings.config import Settings

logger = logging.getLogger(__name__)


def _extract_auth_admin_error_hint(response: httpx.Response) -> Optional[str]:
    try:
        data = response.json()
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    parts: list[str] = []
    for key in ("msg", "message", "error_description", "error", "hint"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    if not parts:
        return None
    text = "; ".join(dict.fromkeys(parts))
    return text[:240]


def _fallback_hint_for_status(status_code: int) -> Optional[str]:
    if status_code in (401, 403):
        return "检查 SUPABASE_SERVICE_ROLE_KEY 是否有效且具备 auth admin 权限（service_role）"
    if status_code == 404:
        return "检查 Supabase Auth 是否启用，且使用的是正确的项目 URL"
    return None


class SupabaseAuthAdminError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 500, hint: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.hint = hint


class SupabaseAuthAdminClient:
    """Thin wrapper around Supabase GoTrue Admin API.

    Notes:
    - Requires SUPABASE_SERVICE_ROLE_KEY
    - Uses /auth/v1/admin/* endpoints (not PostgREST)
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = self._resolve_base_url(settings)
        self._service_role_key = settings.supabase_service_role_key
        if not self._service_role_key:
            raise SupabaseAuthAdminError(
                code="supabase_service_role_key_missing",
                message="Supabase service role key is not configured",
                status_code=500,
                hint="Set SUPABASE_SERVICE_ROLE_KEY",
            )
        self._timeout = settings.http_timeout_seconds

    @staticmethod
    def _resolve_base_url(settings: Settings) -> str:
        if settings.supabase_url:
            return str(settings.supabase_url).rstrip("/")
        if settings.supabase_project_id:
            return f"https://{settings.supabase_project_id}.supabase.co"
        raise SupabaseAuthAdminError(
            code="supabase_not_configured",
            message="Supabase is not configured",
            status_code=500,
            hint="Set SUPABASE_URL or SUPABASE_PROJECT_ID",
        )

    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update({k: str(v) for k, v in extra.items()})
        return headers

    @staticmethod
    def _normalize_user_payload(data: Any) -> Optional[dict[str, Any]]:
        if isinstance(data, dict) and isinstance(data.get("user"), dict):
            return data["user"]
        if isinstance(data, dict):
            return data
        return None

    async def list_users(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        request_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}/auth/v1/admin/users"
        params = {"page": max(int(page), 1), "per_page": max(int(per_page), 1)}
        extra_headers = {"X-Request-Id": request_id} if request_id else None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers(extra_headers), params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase auth admin list users failed status=%s", status)
            extracted_hint = _extract_auth_admin_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_request_failed",
                message="Supabase auth admin request failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase auth admin request error error=%s", type(exc).__name__)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_request_error",
                message="Supabase auth admin request error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_response_invalid",
                message="Supabase auth admin response is not valid JSON",
                status_code=502,
            ) from exc

        # GoTrue may return: {"users":[...]} or just [...]
        if isinstance(data, dict) and isinstance(data.get("users"), list):
            return [row for row in data["users"] if isinstance(row, dict)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    async def get_user(
        self,
        *,
        user_id: str,
        request_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        url = f"{self._base_url}/auth/v1/admin/users/{user_id}"
        extra_headers = {"X-Request-Id": request_id} if request_id else None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers(extra_headers))
                if response.status_code == 404:
                    return None
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase auth admin get user failed status=%s user_id=%s", status, user_id)
            extracted_hint = _extract_auth_admin_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_request_failed",
                message="Supabase auth admin request failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase auth admin request error error=%s", type(exc).__name__)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_request_error",
                message="Supabase auth admin request error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError:
            return None
        return self._normalize_user_payload(data)

    async def update_user(
        self,
        *,
        user_id: str,
        app_metadata: Optional[dict[str, Any]] = None,
        user_metadata: Optional[dict[str, Any]] = None,
        password: Optional[str] = None,
        banned_until: Optional[datetime] = None,
        clear_banned_until: bool = False,
        request_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        url = f"{self._base_url}/auth/v1/admin/users/{user_id}"
        payload: dict[str, Any] = {}
        if app_metadata is not None:
            payload["app_metadata"] = app_metadata
        if user_metadata is not None:
            payload["user_metadata"] = user_metadata
        if password is not None:
            payload["password"] = password
        if clear_banned_until:
            payload["banned_until"] = None
        elif banned_until is not None:
            payload["banned_until"] = banned_until.astimezone(timezone.utc).isoformat()
        if not payload:
            return await self.get_user(user_id=user_id, request_id=request_id)

        extra_headers = {"X-Request-Id": request_id} if request_id else None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # GoTrue supports PUT for admin updates.
                response = await client.put(url, headers=self._headers(extra_headers), json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase auth admin update user failed status=%s user_id=%s", status, user_id)
            extracted_hint = _extract_auth_admin_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_update_failed",
                message="Supabase auth admin update failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase auth admin update error error=%s", type(exc).__name__)
            raise SupabaseAuthAdminError(
                code="supabase_auth_admin_update_error",
                message="Supabase auth admin update error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError:
            return None
        return self._normalize_user_payload(data)
