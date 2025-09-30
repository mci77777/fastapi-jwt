"""策略门中间件 - 限制匿名用户访问敏感端点。"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Pattern

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.auth import AuthenticatedUser
from app.core.exceptions import create_error_response
from app.core.middleware import get_current_trace_id
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


class PolicyGateMiddleware(BaseHTTPMiddleware):
    """策略门中间件 - 限制匿名用户访问敏感端点。"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()

        # 定义匿名用户禁止访问的端点模式
        self.anonymous_restricted_patterns: List[Pattern] = [
            # 管理后台相关端点
            re.compile(r'^/api/v1/admin/.*$'),
            re.compile(r'^/api/v1/base/.*$'),
            re.compile(r'^/api/v1/user/.*$'),
            re.compile(r'^/api/v1/role/.*$'),
            re.compile(r'^/api/v1/menu/.*$'),
            re.compile(r'^/api/v1/api/.*$'),
            re.compile(r'^/api/v1/dept/.*$'),
            re.compile(r'^/api/v1/auditlog/.*$'),

            # 公开分享相关端点
            re.compile(r'^/api/v1/conversations/.+/share$'),
            re.compile(r'^/api/v1/public_shares/.*$'),

            # 批量操作端点
            re.compile(r'^/api/v1/messages/batch$'),
            re.compile(r'^/api/v1/conversations/batch$'),

            # LLM管理端点（仅允许查看模型列表）
            re.compile(r'^/api/v1/llm/models$', re.IGNORECASE),  # POST/PUT/DELETE 禁止
            re.compile(r'^/api/v1/llm/prompts/.*$'),
        ]

        # 定义匿名用户允许的端点（白名单）
        self.anonymous_allowed_patterns: List[Pattern] = [
            # 基础对话功能
            re.compile(r'^/api/v1/messages$'),  # POST 创建消息
            re.compile(r'^/api/v1/messages/[^/]+/events$'),  # GET SSE事件流

            # 获取模型列表（只读）
            re.compile(r'^/api/v1/llm/models$'),  # GET 获取模型列表

            # 健康检查等公共端点
            re.compile(r'^/health$'),
            re.compile(r'^/docs$'),
            re.compile(r'^/openapi\.json$'),
        ]

        # 定义公开端点（无需认证）
        self.public_endpoints: List[Pattern] = [
            # 登录端点
            re.compile(r'^/api/v1/base/access_token$'),

            # 健康探针
            re.compile(r'^/api/v1/healthz$'),
            re.compile(r'^/api/v1/livez$'),
            re.compile(r'^/api/v1/readyz$'),

            # 指标端点
            re.compile(r'^/api/v1/metrics$'),

            # API文档
            re.compile(r'^/docs$'),
            re.compile(r'^/redoc$'),
            re.compile(r'^/openapi\.json$'),
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        # 检查是否是公开端点（无需认证）
        if self._is_public_endpoint(path):
            return await call_next(request)

        # 如果匿名支持未启用，直接通过
        if not self.settings.anon_enabled:
            return await call_next(request)

        # 获取用户信息
        user: Optional[AuthenticatedUser] = getattr(request.state, 'user', None)

        # 如果用户未认证或不是匿名用户，直接通过
        if not user or not user.is_anonymous:
            return await call_next(request)

        # 检查匿名用户访问权限
        # 检查是否在允许列表中
        if self._is_path_allowed_for_anonymous(path, method):
            return await call_next(request)

        # 检查是否在限制列表中
        if self._is_path_restricted_for_anonymous(path, method):
            return self._create_anonymous_restriction_error(path, method)

        # 默认允许通过（保守策略）
        return await call_next(request)

    def _is_public_endpoint(self, path: str) -> bool:
        """检查路径是否是公开端点（无需认证）。"""
        for pattern in self.public_endpoints:
            if pattern.match(path):
                return True
        return False

    def _is_path_allowed_for_anonymous(self, path: str, method: str) -> bool:
        """检查路径是否在匿名用户允许列表中。"""
        for pattern in self.anonymous_allowed_patterns:
            if pattern.match(path):
                # 对于模型端点，只允许GET请求
                if '/llm/models' in path and method != 'GET':
                    return False
                return True
        return False

    def _is_path_restricted_for_anonymous(self, path: str, method: str) -> bool:
        """检查路径是否在匿名用户限制列表中。"""
        for pattern in self.anonymous_restricted_patterns:
            if pattern.match(path):
                return True
        return False

    def _create_anonymous_restriction_error(self, path: str, method: str) -> Response:
        """创建匿名用户访问限制错误响应。"""
        trace_id = get_current_trace_id()

        logger.warning(
            "匿名用户访问受限端点被拒绝 path=%s method=%s trace_id=%s",
            path, method, trace_id
        )

        return create_error_response(
            status_code=403,
            code="ANONYMOUS_ACCESS_DENIED",
            message="Anonymous users cannot access this endpoint",
            hint="Please upgrade your account to access this feature",
            headers={}
        )


def get_anonymous_restricted_endpoints() -> List[str]:
    """获取匿名用户受限端点列表（用于文档生成）。"""
    return [
        # 管理后台
        "GET/POST/PUT/DELETE /api/v1/admin/*",
        "GET/POST/PUT/DELETE /api/v1/base/*",
        "GET/POST/PUT/DELETE /api/v1/user/*",
        "GET/POST/PUT/DELETE /api/v1/role/*",
        "GET/POST/PUT/DELETE /api/v1/menu/*",
        "GET/POST/PUT/DELETE /api/v1/api/*",
        "GET/POST/PUT/DELETE /api/v1/dept/*",
        "GET/POST/PUT/DELETE /api/v1/auditlog/*",

        # 公开分享
        "POST /api/v1/conversations/{id}/share",
        "GET/POST/PUT/DELETE /api/v1/public_shares/*",

        # 批量操作
        "POST /api/v1/messages/batch",
        "POST /api/v1/conversations/batch",

        # LLM管理（除了GET /api/v1/llm/models）
        "POST/PUT/DELETE /api/v1/llm/models",
        "GET/POST/PUT/DELETE /api/v1/llm/prompts/*",
    ]


def get_anonymous_allowed_endpoints() -> List[str]:
    """获取匿名用户允许端点列表（用于文档生成）。"""
    return [
        # 基础对话功能
        "POST /api/v1/messages",
        "GET /api/v1/messages/{message_id}/events",

        # 模型查询
        "GET /api/v1/llm/models",

        # 公共端点
        "GET /health",
        "GET /docs",
        "GET /openapi.json",
    ]
