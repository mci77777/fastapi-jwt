"""自定义中间件集合。"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER_NAME = "X-Request-Id"

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成或透传 Request ID（SSOT：X-Request-Id）。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER_NAME)
        request_id = incoming or uuid.uuid4().hex
        token = _request_id_ctx.set(request_id)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER_NAME] = request_id
        _request_id_ctx.reset(token)
        return response


def get_current_request_id() -> str | None:
    """向日志等场景暴露当前 Request ID。"""

    return _request_id_ctx.get()


def set_current_request_id(request_id: str) -> Token[str | None]:
    """为非 HTTP 调用链（如 BackgroundTasks）绑定 request_id。"""

    return _request_id_ctx.set(request_id)


def reset_current_request_id(token: Token[str | None]) -> None:
    """重置 set_current_request_id() 绑定的 request_id。"""

    _request_id_ctx.reset(token)


__all__ = [
    "REQUEST_ID_HEADER_NAME",
    "RequestIDMiddleware",
    "get_current_request_id",
    "reset_current_request_id",
    "set_current_request_id",
]
