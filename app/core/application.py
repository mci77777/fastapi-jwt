"""FastAPI 应用初始化逻辑。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.settings.config import get_settings


@asynccontextmanager
def lifespan(_: FastAPI):
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=settings.cors_allow_credentials,
    )

    app.include_router(api_router, prefix="/api")
    return app
