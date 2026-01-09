"""全局异常处理。"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.middleware import get_current_request_id

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    hint: Optional[str] = None,
) -> JSONResponse:
    """创建统一格式的错误响应。"""
    from app.core.middleware import get_current_request_id

    if request_id is None:
        request_id = get_current_request_id() or uuid.uuid4().hex

    payload: Dict[str, Any] = {
        "status": status_code,
        "code": code,
        # Dashboard 前端兼容字段：axios 拦截器优先读取 msg
        "msg": f"{message}（{hint}）" if hint else message,
        "message": message,
        "request_id": request_id,
    }
    if hint is not None:
        payload["hint"] = hint

    return JSONResponse(status_code=status_code, content=payload, headers=headers or {})


def _build_detail(detail: Any, default_code: str) -> Dict[str, Any]:
    """构建统一的错误详情格式。"""
    if isinstance(detail, dict):
        # 如果已经是字典格式，确保包含必要字段
        result = detail.copy()
        result.setdefault("status", 500)
        result.setdefault("code", default_code)
        if "message" not in result and isinstance(result.get("msg"), str) and result.get("msg"):
            result["message"] = result["msg"]
        result.setdefault("message", default_code.replace("_", " "))
        if "msg" not in result and isinstance(result.get("message"), str) and result.get("message"):
            result["msg"] = result["message"]
        return result
    if detail is None:
        payload = {"status": 500, "code": default_code, "message": default_code.replace("_", " ")}
        payload["msg"] = payload["message"]
        return payload
    payload = {"status": 500, "code": default_code, "message": str(detail)}
    payload["msg"] = payload["message"]
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    """注册 FastAPI 全局异常处理。"""

    from app.services.supabase_admin import SupabaseAdminError

    @app.exception_handler(SupabaseAdminError)
    async def supabase_admin_exception_handler(request: Request, exc: SupabaseAdminError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_current_request_id() or uuid.uuid4().hex
        return create_error_response(
            status_code=int(getattr(exc, "status_code", 500) or 500),
            code=str(getattr(exc, "code", "supabase_error") or "supabase_error"),
            message=str(exc) or "Supabase error",
            request_id=request_id,
            hint=getattr(exc, "hint", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_current_request_id() or uuid.uuid4().hex

        # 额外字段（extra=forbid / additionalProperties=false）常见错误类型：extra_forbidden
        try:
            extra_fields: list[str] = []
            for item in exc.errors():
                if isinstance(item, dict) and item.get("type") == "extra_forbidden":
                    loc = item.get("loc") or ()
                    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                        extra_fields.append(str(loc[-1]))
            if extra_fields:
                logger.warning(
                    "Request validation failed (extra_forbidden) extra_fields=%s request_id=%s path=%s",
                    ",".join(sorted(set(extra_fields))),
                    request_id,
                    request.url.path,
                )
        except Exception:
            # 不阻塞异常响应
            pass

        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "msg": "请求参数错误",
                "request_id": request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_current_request_id() or uuid.uuid4().hex
        payload = _build_detail(exc.detail, default_code="http_error")

        # 确保状态码正确
        payload["status"] = exc.status_code

        # 确保包含 request_id
        payload["request_id"] = request_id
        payload.setdefault("msg", payload.get("message"))

        # 对于401错误，确保不泄露敏感信息
        if exc.status_code == 401:
            # 保持JWT验证器提供的错误信息，但确保格式统一
            if not isinstance(exc.detail, dict):
                payload = {
                    "status": 401,
                    "code": "unauthorized",
                    "msg": "Authentication required",
                    "message": "Authentication required",
                    "request_id": request_id,
                }

        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D401
        request_id = getattr(request.state, "request_id", None) or get_current_request_id() or uuid.uuid4().hex
        logger.exception("Unhandled exception request_id=%s path=%s", request_id, request.url.path)
        payload = {
            "status": 500,
            "code": "internal_server_error",
            "msg": "Internal server error",
            "message": "Internal server error",
            "request_id": request_id,
        }
        return JSONResponse(status_code=500, content=payload)
