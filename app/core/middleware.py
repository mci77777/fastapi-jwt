"""自定义中间件集合。"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


class TraceIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成或透传 Trace ID。"""

    def __init__(self, app: ASGIApp, header_name: str) -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(self._header_name)
        trace_id = incoming or uuid.uuid4().hex
        token = _trace_id_ctx.set(trace_id)
        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers[self._header_name] = trace_id
        _trace_id_ctx.reset(token)
        return response


def get_current_trace_id() -> str | None:
    """向日志等场景暴露当前 Trace ID。"""

    return _trace_id_ctx.get()
