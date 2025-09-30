"""FastAPI 应用初始化逻辑。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import api_router
from app.core.exceptions import register_exception_handlers
from app.core.middleware import TraceIDMiddleware
from app.core.policy_gate import PolicyGateMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.services.ai_service import AIService, MessageEventBroker
from app.settings.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """暂留钩子，后续可在此注册连接池等资源。"""

    yield


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    if settings.force_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    if settings.allowed_hosts and settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.add_middleware(TraceIDMiddleware, header_name=settings.trace_header_name)
    app.add_middleware(PolicyGateMiddleware)  # 策略门中间件，在限流之前
    app.add_middleware(RateLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=settings.cors_allow_credentials,
    )

    app.state.message_broker = MessageEventBroker()
    app.state.ai_service = AIService()

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api")
    return app
