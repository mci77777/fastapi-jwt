"""全局异常处理。"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.middleware import get_current_trace_id

logger = logging.getLogger(__name__)


def _build_detail(detail: Any, default_code: str) -> Dict[str, Any]:
    if isinstance(detail, dict):
        return detail
    if detail is None:
        return {"code": default_code, "message": default_code.replace("_", " ")}
    return {"code": default_code, "message": str(detail)}


def register_exception_handlers(app: FastAPI) -> None:
    """注册 FastAPI 全局异常处理。"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
        payload = _build_detail(exc.detail, default_code="http_error")
        payload.setdefault("message", exc.detail if isinstance(exc.detail, str) else "")
        payload.setdefault("code", "http_error")
        payload["trace_id"] = trace_id
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D401
        trace_id = getattr(request.state, "trace_id", None) or get_current_trace_id()
        logger.exception("Unhandled exception trace_id=%s path=%s", trace_id, request.url.path)
        payload = {
            "code": "internal_server_error",
            "message": "Internal server error",
            "trace_id": trace_id,
        }
        return JSONResponse(status_code=500, content=payload)
