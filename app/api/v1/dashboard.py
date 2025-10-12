"""Dashboard WebSocket 和统计 API 路由。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.auth.jwt_verifier import get_jwt_verifier
from app.core.exceptions import create_error_response
from app.services.dashboard_broker import DashboardBroker
from app.services.log_collector import LogCollector
from app.services.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ============================================================================
# WebSocket 端点
# ============================================================================


async def get_current_user_ws(token: str) -> AuthenticatedUser:
    """WebSocket JWT 验证（从查询参数获取 token）。

    Args:
        token: JWT token

    Returns:
        已认证用户

    Raises:
        HTTPException: 验证失败
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Token is required"},
        )

    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        return user
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("WebSocket JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid token"},
        )


@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    request: Request,
    token: str = Query(..., description="JWT token"),
) -> None:
    """Dashboard WebSocket 端点，实时推送统计数据。

    Args:
        websocket: WebSocket 连接
        request: FastAPI 请求对象
        token: JWT token（查询参数）

    连接流程:
        1. JWT 验证
        2. 检查用户类型（匿名用户禁止访问）
        3. 接受连接
        4. 每 10 秒推送一次统计数据
        5. 断线时清理连接
    """
    # JWT 验证
    try:
        user = await get_current_user_ws(token)
    except HTTPException as exc:
        await websocket.close(code=1008, reason="Unauthorized")
        logger.warning("WebSocket connection rejected: unauthorized")
        return

    # 检查用户类型（匿名用户禁止访问）
    if user.user_type == "anonymous":
        await websocket.close(code=1008, reason="Anonymous users not allowed")
        logger.warning("WebSocket connection rejected: anonymous user uid=%s", user.uid)
        return

    # 接受连接
    await websocket.accept()
    logger.info("WebSocket connection accepted uid=%s user_type=%s", user.uid, user.user_type)

    # 获取服务
    broker: DashboardBroker = request.app.state.dashboard_broker

    try:
        while True:
            # 获取统计数据
            stats = await broker.get_dashboard_stats(time_window="24h")

            # 推送数据
            await websocket.send_json(
                {
                    "type": "stats_update",
                    "data": stats,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # 等待 10 秒
            await asyncio.sleep(10)

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed uid=%s", user.uid)
    except Exception as exc:
        logger.exception("WebSocket error uid=%s error=%s", user.uid, exc)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass


# ============================================================================
# REST API 端点
# ============================================================================


class DashboardStatsResponse(BaseModel):
    """Dashboard 统计数据响应。"""

    daily_active_users: int = Field(..., description="日活用户数")
    ai_requests: Dict[str, Any] = Field(..., description="AI 请求统计")
    token_usage: Optional[int] = Field(None, description="Token 使用量（后续追加）")
    api_connectivity: Dict[str, Any] = Field(..., description="API 连通性")
    jwt_availability: Dict[str, Any] = Field(..., description="JWT 可获取性")


class LogEntry(BaseModel):
    """日志条目。"""

    timestamp: str = Field(..., description="时间戳")
    level: str = Field(..., description="日志级别")
    level_num: int = Field(..., description="日志级别数值")
    user_id: Optional[str] = Field(None, description="用户 ID")
    message: str = Field(..., description="日志消息")
    module: str = Field(..., description="模块名")
    function: str = Field(..., description="函数名")
    line: int = Field(..., description="行号")


@router.get("/stats/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    request: Request,
    time_window: str = Query("24h", regex="^(1h|24h|7d)$", description="时间窗口"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DashboardStatsResponse:
    """获取 Dashboard 聚合统计数据。

    Args:
        request: FastAPI 请求对象
        time_window: 时间窗口 (1h, 24h, 7d)
        current_user: 当前用户

    Returns:
        Dashboard 统计数据
    """
    broker: DashboardBroker = request.app.state.dashboard_broker
    stats = await broker.get_dashboard_stats(time_window)
    return DashboardStatsResponse(**stats)


@router.get("/stats/daily-active-users")
async def get_daily_active_users(
    request: Request,
    time_window: str = Query("24h", regex="^(1h|24h|7d)$", description="时间窗口"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取日活用户数。

    Args:
        request: FastAPI 请求对象
        time_window: 时间窗口
        current_user: 当前用户

    Returns:
        日活用户数
    """
    collector: MetricsCollector = request.app.state.metrics_collector
    count = await collector._get_daily_active_users(time_window)
    return {"time_window": time_window, "count": count}


@router.get("/stats/ai-requests")
async def get_ai_requests(
    request: Request,
    time_window: str = Query("24h", regex="^(1h|24h|7d)$", description="时间窗口"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 AI 请求统计。

    Args:
        request: FastAPI 请求对象
        time_window: 时间窗口
        current_user: 当前用户

    Returns:
        AI 请求统计
    """
    collector: MetricsCollector = request.app.state.metrics_collector
    stats = await collector._get_ai_requests(time_window)
    return {"time_window": time_window, **stats}


@router.get("/stats/api-connectivity")
async def get_api_connectivity(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 API 连通性状态。

    Args:
        request: FastAPI 请求对象
        current_user: 当前用户

    Returns:
        API 连通性状态
    """
    collector: MetricsCollector = request.app.state.metrics_collector
    return await collector._get_api_connectivity()


@router.get("/stats/jwt-availability")
async def get_jwt_availability(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 JWT 可获取性。

    Args:
        request: FastAPI 请求对象
        current_user: 当前用户

    Returns:
        JWT 可获取性
    """
    collector: MetricsCollector = request.app.state.metrics_collector
    return await collector._get_jwt_availability()


@router.get("/logs/recent")
async def get_recent_logs(
    request: Request,
    level: str = Query("WARNING", regex="^(ERROR|WARNING|INFO)$", description="最低日志级别"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回条数"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取最近日志。

    Args:
        request: FastAPI 请求对象
        level: 最低日志级别
        limit: 最大返回条数
        current_user: 当前用户

    Returns:
        日志列表
    """
    # 仅管理员可查看日志（简化实现，后续可扩展 RBAC）
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot access logs"},
        )

    log_collector: LogCollector = request.app.state.log_collector
    logs = log_collector.get_recent_logs(level=level, limit=limit)
    return {"level": level, "limit": limit, "count": len(logs), "logs": logs}

