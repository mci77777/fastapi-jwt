"""Supabase admin client (service role) for PostgREST reads."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.settings.config import Settings

logger = logging.getLogger(__name__)


class SupabaseAdminError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 500, hint: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.hint = hint


class SupabaseAdminClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = self._resolve_base_url(settings)
        self._service_role_key = settings.supabase_service_role_key
        if not self._service_role_key:
            raise SupabaseAdminError(
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
        raise SupabaseAdminError(
            code="supabase_not_configured",
            message="Supabase is not configured",
            status_code=500,
            hint="Set SUPABASE_URL or SUPABASE_PROJECT_ID",
        )

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }

    async def fetch_one_by_user_id(
        self,
        *,
        table: str,
        user_id: str,
        select: str = "*",
    ) -> Optional[dict[str, Any]]:
        """Fetch a single row from a table keyed by user_id.

        Returns None when row is missing.
        """
        url = f"{self._base_url}/rest/v1/{table}"
        params = {"select": select, "user_id": f"eq.{user_id}", "limit": 1}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers(), params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase admin request failed table=%s status=%s", table, status)
            raise SupabaseAdminError(
                code="supabase_request_failed",
                message="Supabase request failed",
                status_code=status,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase admin request error table=%s error=%s", table, type(exc).__name__)
            raise SupabaseAdminError(
                code="supabase_request_error",
                message="Supabase request error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover
            raise SupabaseAdminError(
                code="supabase_response_invalid",
                message="Supabase response is not valid JSON",
                status_code=502,
            ) from exc

        if not isinstance(data, list):  # pragma: no cover
            raise SupabaseAdminError(
                code="supabase_response_invalid",
                message="Supabase response is not a list",
                status_code=502,
            )

        if not data:
            return None

        row = data[0]
        if not isinstance(row, dict):  # pragma: no cover
            raise SupabaseAdminError(
                code="supabase_response_invalid",
                message="Supabase row is not an object",
                status_code=502,
            )
        return row

