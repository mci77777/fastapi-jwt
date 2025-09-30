"""全局异常处理。"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.middleware import get_current_trace_id

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    trace_id: str = None,
    headers: Dict[str, str] = None
) -> JSONResponse:
    """创建统一格式的错误响应。"""
    from app.core.middleware import get_current_trace_id

    if trace_id is None:
        trace_id = get_current_trace_id()

    payload = {
        "status": status_code,
        "code": code,
        "message": message,
        "trace_id": trace_id
    }

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=headers or {}
    )


def _build_detail(detail: Any, default_code: str) -> Dict[str, Any]:
    """构建统一的错误详情格式。"""
    if isinstance(detail, dict):
        # 如果已经是字典格式，确保包含必要字段
        result = detail.copy()
        result.setdefault("status", 500)
        result.setdefault("code", default_code)
        result.setdefault("message", default_code.replace("_", " "))
        return result
    if detail is None:
        return {
            "status": 500,
            "code": default_code,
            "message": default_code.replace("_", " ")
        }
    return {
        "status": 500,
        "code": default_code,
        "message": str(detail)
    }


def register_exception_handlers(app: FastAPI) -> None:
    """注册 FastAPI 全局异常处理。"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
        payload = _build_detail(exc.detail, default_code="http_error")

        # 确保状态码正确
        payload["status"] = exc.status_code

        # 确保包含trace_id
        payload["trace_id"] = trace_id

        # 对于401错误，确保不泄露敏感信息
        if exc.status_code == 401:
            # 保持JWT验证器提供的错误信息，但确保格式统一
            if not isinstance(exc.detail, dict):
                payload = {
                    "status": 401,
                    "code": "unauthorized",
                    "message": "Authentication required",
                    "trace_id": trace_id
                }

        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D401
        trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
        logger.exception("Unhandled exception trace_id=%s path=%s", trace_id, request.url.path)
        payload = {
            "status": 500,
            "code": "internal_server_error",
            "message": "Internal server error",
            "trace_id": trace_id,
        }
        return JSONResponse(status_code=500, content=payload)
