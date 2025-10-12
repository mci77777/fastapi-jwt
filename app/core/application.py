"""FastAPI 应用初始化逻辑。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import api_router
from app.core.exceptions import register_exception_handlers
from app.core.middleware import TraceIDMiddleware
from app.core.policy_gate import PolicyGateMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.services.ai_config_service import AIConfigService
from app.services.ai_service import AIService, MessageEventBroker
from app.services.dashboard_broker import DashboardBroker
from app.services.jwt_test_service import JWTTestService
from app.services.log_collector import LogCollector
from app.services.metrics_collector import MetricsCollector
from app.services.model_mapping_service import ModelMappingService
from app.services.monitor_service import EndpointMonitor
from app.services.sync_service import SyncService
from app.settings.config import get_settings
from app.db import SQLiteManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """暂留钩子，后续可在此注册连接池等资源。"""

    settings = get_settings()
    sqlite_manager = SQLiteManager(Path("db.sqlite3"))
    await sqlite_manager.init()
    app.state.sqlite_manager = sqlite_manager
    storage_dir = Path("storage") / "ai_runtime"
    app.state.ai_config_service = AIConfigService(sqlite_manager, settings, storage_dir)
    app.state.endpoint_monitor = EndpointMonitor(app.state.ai_config_service)
    app.state.model_mapping_service = ModelMappingService(app.state.ai_config_service, storage_dir)
    app.state.jwt_test_service = JWTTestService(app.state.ai_config_service, settings, storage_dir)

    # Dashboard 服务层（Phase 1）
    app.state.log_collector = LogCollector(max_size=100)
    app.state.metrics_collector = MetricsCollector(sqlite_manager, app.state.endpoint_monitor)
    app.state.dashboard_broker = DashboardBroker(app.state.metrics_collector)
    app.state.sync_service = SyncService(sqlite_manager)

    try:
        yield
    finally:
        # 清理资源
        monitor = getattr(app.state, "endpoint_monitor", None)
        if monitor is not None:
            await monitor.stop()

        log_collector = getattr(app.state, "log_collector", None)
        if log_collector is not None:
            log_collector.shutdown()

        await sqlite_manager.close()


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
