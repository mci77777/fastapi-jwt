"""Supabase admin client (service role) for PostgREST reads."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.settings.config import Settings

logger = logging.getLogger(__name__)


def _extract_postgrest_error_hint(response: httpx.Response) -> Optional[str]:
    try:
        data = response.json()
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    parts: list[str] = []
    for key in ("message", "hint", "details", "error_description", "error"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    code = data.get("code")
    if isinstance(code, str) and code.strip():
        parts.append(f"code={code.strip()}")

    if not parts:
        return None

    text = "; ".join(dict.fromkeys(parts))  # preserve order + dedupe
    return text[:240]


def _extract_postgrest_error_code(response: httpx.Response) -> Optional[str]:
    try:
        data = response.json()
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    code = data.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    return None


def _merge_hints(primary: Optional[str], extra: Optional[str]) -> Optional[str]:
    primary_text = (primary or "").strip()
    extra_text = (extra or "").strip()
    if not primary_text:
        return extra_text or None
    if not extra_text:
        return primary_text or None
    return f"{primary_text}; {extra_text}"[:240]


def _fallback_hint_for_status(status_code: int, *, table: Optional[str] = None) -> Optional[str]:
    if status_code in (401, 403):
        return "检查 SUPABASE_SERVICE_ROLE_KEY 是否有效且具备 service_role 权限"
    if status_code == 404 and table:
        return f"检查 Supabase 是否已创建表 {table} 且已开放 PostgREST"
    return None


def _map_postgrest_code_to_error(postgrest_code: Optional[str], *, table: str) -> tuple[Optional[str], Optional[str]]:
    """Map PostgREST/PG error codes to a stable dashboard error code + hint."""
    if not postgrest_code:
        return None, None
    code = str(postgrest_code).strip()
    if code == "PGRST205":
        return "supabase_table_missing", "数据源缺失或未初始化，请完成 Supabase 初始化后重试"
    # PGSQL foreign_key_violation
    if code == "23503":
        return (
            "supabase_foreign_key_violation",
            "该用户不存在或已删除，无法执行该操作",
        )
    return None, None


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
    def _parse_content_range_total(value: Optional[str]) -> Optional[int]:
        """Parse PostgREST Content-Range total like "0-0/123"."""
        if not value:
            return None
        if "/" not in value:
            return None
        total_text = value.split("/", 1)[-1].strip()
        try:
            return int(total_text)
        except Exception:
            return None

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
            postgrest_code = _extract_postgrest_error_code(exc.response)
            extracted_hint = _extract_postgrest_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status, table=table)
            mapped_code, mapped_hint = _map_postgrest_code_to_error(postgrest_code, table=table)
            if mapped_code:
                raise SupabaseAdminError(
                    code=mapped_code,
                    message="Supabase request failed",
                    status_code=status,
                    hint=_merge_hints(hint, mapped_hint),
                ) from exc
            raise SupabaseAdminError(
                code="supabase_request_failed",
                message="Supabase request failed",
                status_code=status,
                hint=hint,
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

    async def upsert_one(
        self,
        *,
        table: str,
        values: dict[str, Any],
        on_conflict: str = "user_id",
    ) -> Optional[dict[str, Any]]:
        """Upsert a single row and return representation (best-effort).

        Notes:
        - Uses PostgREST upsert semantics: Prefer: resolution=merge-duplicates.
        - Returns the first row when representation is returned as a list.
        """
        url = f"{self._base_url}/rest/v1/{table}"
        params = {"on_conflict": on_conflict}
        headers = self._headers({"Prefer": "resolution=merge-duplicates,return=representation"})

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, params=params, json=values)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase admin upsert failed table=%s status=%s", table, status)
            postgrest_code = _extract_postgrest_error_code(exc.response)
            extracted_hint = _extract_postgrest_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status, table=table)
            mapped_code, mapped_hint = _map_postgrest_code_to_error(postgrest_code, table=table)
            if mapped_code:
                raise SupabaseAdminError(
                    code=mapped_code,
                    message="Supabase upsert failed",
                    status_code=status,
                    hint=_merge_hints(hint, mapped_hint),
                ) from exc
            raise SupabaseAdminError(
                code="supabase_upsert_failed",
                message="Supabase upsert failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase admin upsert error table=%s error=%s", table, type(exc).__name__)
            raise SupabaseAdminError(
                code="supabase_upsert_error",
                message="Supabase upsert error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError:
            return None

        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    async def update_one_by_user_id(
        self,
        *,
        table: str,
        user_id: str,
        values: dict[str, Any],
        select: str = "*",
    ) -> Optional[dict[str, Any]]:
        """PATCH update by user_id and return representation (best-effort)."""
        url = f"{self._base_url}/rest/v1/{table}"
        params = {"user_id": f"eq.{user_id}", "select": select}
        headers = self._headers({"Prefer": "return=representation"})

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.patch(url, headers=headers, params=params, json=values)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase admin update failed table=%s status=%s", table, status)
            postgrest_code = _extract_postgrest_error_code(exc.response)
            extracted_hint = _extract_postgrest_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status, table=table)
            mapped_code, mapped_hint = _map_postgrest_code_to_error(postgrest_code, table=table)
            if mapped_code:
                raise SupabaseAdminError(
                    code=mapped_code,
                    message="Supabase update failed",
                    status_code=status,
                    hint=_merge_hints(hint, mapped_hint),
                ) from exc
            raise SupabaseAdminError(
                code="supabase_update_failed",
                message="Supabase update failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase admin update error table=%s error=%s", table, type(exc).__name__)
            raise SupabaseAdminError(
                code="supabase_update_error",
                message="Supabase update error",
                status_code=502,
            ) from exc

        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    async def fetch_list(
        self,
        *,
        table: str,
        filters: Optional[dict[str, Any]] = None,
        select: str = "*",
        order: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        with_count: bool = False,
    ) -> tuple[list[dict[str, Any]], Optional[int]]:
        """Fetch rows from a table with optional exact count.

        Notes:
        - PostgREST count is returned in Content-Range when Prefer: count=exact is set.
        """
        url = f"{self._base_url}/rest/v1/{table}"

        params: dict[str, Any] = {"select": select, "limit": int(limit), "offset": int(offset)}
        if order:
            params["order"] = str(order)
        if filters:
            params.update({k: str(v) for k, v in filters.items() if v is not None})

        headers = self._headers({"Prefer": "count=exact"} if with_count else None)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = int(getattr(exc.response, "status_code", 0) or 0) or 502
            logger.warning("Supabase admin list failed table=%s status=%s", table, status)
            postgrest_code = _extract_postgrest_error_code(exc.response)
            extracted_hint = _extract_postgrest_error_hint(exc.response)
            hint = extracted_hint or _fallback_hint_for_status(status, table=table)
            mapped_code, mapped_hint = _map_postgrest_code_to_error(postgrest_code, table=table)
            if mapped_code:
                raise SupabaseAdminError(
                    code=mapped_code,
                    message="Supabase request failed",
                    status_code=status,
                    hint=_merge_hints(hint, mapped_hint),
                ) from exc
            raise SupabaseAdminError(
                code="supabase_request_failed",
                message="Supabase request failed",
                status_code=status,
                hint=hint,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Supabase admin list error table=%s error=%s", table, type(exc).__name__)
            raise SupabaseAdminError(
                code="supabase_request_error",
                message="Supabase request error",
                status_code=502,
            ) from exc

        total: Optional[int] = None
        if with_count:
            total = self._parse_content_range_total(response.headers.get("content-range"))

        try:
            data = response.json()
        except ValueError:
            return [], total

        if not isinstance(data, list):
            return [], total

        items: list[dict[str, Any]] = [row for row in data if isinstance(row, dict)]
        return items, total

    async def count_rows(
        self,
        *,
        table: str,
        filters: Optional[dict[str, Any]] = None,
    ) -> int:
        """Count rows using Prefer: count=exact (best-effort)."""
        _, total = await self.fetch_list(
            table=table,
            filters=filters,
            select="user_id",
            limit=1,
            offset=0,
            with_count=True,
        )
        return int(total or 0)
