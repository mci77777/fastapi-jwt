"""Dashboard WebSocket 和统计 API 路由。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.auth.dashboard_access import is_dashboard_admin_user
from app.db import SQLiteManager, get_sqlite_manager
from app.auth.jwt_verifier import get_jwt_verifier
from app.log import logger
from app.services.dashboard_broker import DashboardBroker
from app.services.log_collector import LogCollector
from app.services.llm_model_registry import LlmModelRegistry
from app.services.metrics_collector import MetricsCollector
from app.services.model_mapping_service import ModelMappingService, normalize_scope_type

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
        logger.warning("WebSocket JWT verification failed: token is empty")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Token is required"},
        )

    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        return user
    except HTTPException as exc:
        logger.warning("WebSocket JWT verification failed: status=%s", exc.status_code)
        raise
    except Exception as exc:
        logger.exception("WebSocket JWT verification failed: unexpected error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid token"},
        ) from exc


@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token"),
) -> None:
    """Dashboard WebSocket 端点，实时推送统计数据。

    Args:
        websocket: WebSocket 连接
        token: JWT token（查询参数）

    连接流程:
        1. 接受连接
        2. JWT 验证
        3. 检查用户类型（匿名用户禁止访问）
        4. 注册到连接池
        5. 每 10 秒推送一次统计数据
        6. 断线时清理连接
    """
    # 先接受连接（必须在任何操作之前）
    await websocket.accept()

    # JWT 验证
    try:
        user = await get_current_user_ws(token)
    except HTTPException as exc:
        await websocket.close(code=1008, reason="Unauthorized")
        logger.warning("WebSocket connection rejected: unauthorized")
        return
    except Exception as exc:
        logger.exception("WebSocket JWT verification error: %s", exc)
        await websocket.close(code=1011, reason="Internal server error")
        return

    # 检查用户类型（匿名用户禁止访问）
    if user.user_type == "anonymous":
        await websocket.close(code=1008, reason="Anonymous users not allowed")
        logger.warning("WebSocket connection rejected: anonymous user uid=%s", user.uid)
        return

    logger.info("WebSocket connection accepted uid=%s user_type=%s", user.uid, user.user_type)

    # 获取服务（从 websocket.app.state）
    broker: DashboardBroker = websocket.app.state.dashboard_broker

    # 注册连接到连接池
    await broker.add_connection(user.uid, websocket)

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
    finally:
        # 确保无论如何都清理连接
        await broker.remove_connection(user.uid)


# ============================================================================
# REST API 端点
# ============================================================================


class DashboardStatsResponse(BaseModel):
    """Dashboard 统计数据响应。"""

    daily_active_users: int = Field(..., description="日活用户数")
    ai_requests: Dict[str, Any] = Field(..., description="AI 请求统计")
    token_usage: Optional[int] = Field(None, description="Token 使用量（后续追加）")
    api_connectivity: Dict[str, Any] = Field(..., description="API 连通性")
    mapped_models: Dict[str, Any] = Field(..., description="映射模型可用性摘要")
    e2e_mapped_models: Optional[Dict[str, Any]] = Field(None, description="每日 E2E 映射模型可用性")
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
    request_id: Optional[str] = Field(None, description="请求链路 ID（X-Request-Id）")


class RequestRawLogIn(BaseModel):
    """前端请求 raw 日志（脱敏后）。"""

    request_id: Optional[str] = Field(None, max_length=128)
    kind: Optional[str] = Field(None, max_length=32)
    method: Optional[str] = Field(None, max_length=16)
    url: Optional[str] = Field(None, max_length=2048)
    status: Optional[str] = Field(None, max_length=32)
    duration_ms: Optional[int] = Field(None, ge=0, le=60_000)
    request_raw: Optional[str] = Field(None, max_length=50_000)
    response_raw: Optional[str] = Field(None, max_length=50_000)
    error: Optional[str] = Field(None, max_length=50_000)
    created_at: Optional[str] = Field(None, max_length=64)


@router.get("/stats/dashboard")
async def get_dashboard_stats(
    request: Request,
    time_window: str = Query("24h", regex="^(1h|24h|7d)$", description="时间窗口"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 Dashboard 聚合统计数据。

    Args:
        request: FastAPI 请求对象
        time_window: 时间窗口 (1h, 24h, 7d)
        current_user: 当前用户

    Returns:
        Dashboard 统计数据（包装在统一响应格式中）
    """
    broker: DashboardBroker = request.app.state.dashboard_broker
    stats = await broker.get_dashboard_stats(time_window)
    return {"code": 200, "data": stats, "msg": "success"}


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

    series: list[int] = []
    if time_window == "7d":
        # 当前仅支持按天粒度序列，避免在 1h/24h 下渲染伪造曲线。
        series = await collector.get_daily_active_users_series(days=7)

    return {
        "time_window": time_window,
        "count": count,
        "granularity": "day" if series else None,
        "series": series,
    }


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


def _calculate_start_date(time_window: str) -> str:
    """计算按天聚合统计的起始日期（ISO 8601 日期字符串）。"""
    now = datetime.now()
    if time_window == "7d":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(hours=24)
    return start_time.date().isoformat()

@router.get("/stats/mapped-models")
async def get_mapped_models_stats(
    request: Request,
    time_window: str = Query("24h", regex="^(24h|7d)$", description="时间窗口（按天聚合：24h/7d）"),
    include_inactive: bool = Query(default=False, description="是否包含未激活映射（默认否）"),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取映射模型可用性 + 调用统计（Dashboard 使用）。"""

    mapping_service = getattr(request.app.state, "model_mapping_service", None)
    registry = getattr(request.app.state, "llm_model_registry", None)
    if not isinstance(mapping_service, ModelMappingService) or not isinstance(registry, LlmModelRegistry):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service_unavailable")

    try:
        mappings = await mapping_service.list_mappings()
    except Exception:
        mappings = []

    scope_priority = ("mapping", "global")
    selected_by_key: dict[str, dict[str, Any]] = {}
    best_score: dict[str, tuple[int, str]] = {}

    for item in mappings:
        if not isinstance(item, dict):
            continue
        scope_type = normalize_scope_type(item.get("scope_type"))
        if scope_type not in scope_priority:
            continue
        if not include_inactive and not bool(item.get("is_active", True)):
            continue

        scope_key = str(item.get("scope_key") or "").strip()
        if not scope_key:
            continue

        pri = scope_priority.index(scope_type) if scope_type in scope_priority else 99
        updated_at = str(item.get("updated_at") or "")

        current = best_score.get(scope_key)
        if current is None or pri < current[0] or (pri == current[0] and updated_at > current[1]):
            best_score[scope_key] = (pri, updated_at)
            selected_by_key[scope_key] = item

    keys = sorted(selected_by_key.keys())

    # 聚合调用统计（按“客户端请求的 model key”口径）
    start_date = _calculate_start_date(time_window)
    db = get_sqlite_manager(request.app)
    raw_rows = await db.fetchall(
        """
        SELECT
            CASE
              WHEN instr(model, ':') > 0 THEN substr(model, instr(model, ':') + 1)
              ELSE model
            END as model_key,
            SUM(count) as calls_total,
            COUNT(DISTINCT user_id) as unique_users,
            SUM(success_count) as success_total,
            SUM(error_count) as error_total,
            SUM(total_latency_ms) as latency_total
        FROM ai_request_stats
        WHERE request_date >= ?
        GROUP BY model_key
        """,
        [start_date],
    )

    stats_by_key: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        model_key = str(row.get("model_key") or "").strip()
        if not model_key:
            continue
        stats_by_key[model_key] = {
            "calls_total": int(row.get("calls_total") or 0),
            "unique_users": int(row.get("unique_users") or 0),
            "success_total": int(row.get("success_total") or 0),
            "error_total": int(row.get("error_total") or 0),
            "latency_total": float(row.get("latency_total") or 0.0),
        }

    def _finalize_stats(model_key: str) -> dict[str, Any]:
        bucket = stats_by_key.get(model_key)
        if not bucket:
            return {"calls_total": 0, "unique_users": 0, "success_rate": 0.0, "avg_latency_ms": 0.0}

        calls_total = int(bucket.get("calls_total") or 0)
        success_total = int(bucket.get("success_total") or 0)
        latency_total = float(bucket.get("latency_total") or 0.0)
        unique_users = int(bucket.get("unique_users") or 0)

        success_rate = round((success_total / calls_total) * 100.0, 2) if calls_total > 0 else 0.0
        avg_latency_ms = round((latency_total / calls_total), 2) if calls_total > 0 else 0.0
        return {
            "calls_total": calls_total,
            "unique_users": int(unique_users),
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency_ms,
        }

    rows: list[dict[str, Any]] = []
    available = 0
    for key in keys:
        selected = selected_by_key.get(key) or {}
        scope_type = normalize_scope_type(selected.get("scope_type"))
        row: dict[str, Any] = {
            "model_key": key,
            "scope_type": scope_type or None,
            "availability": False,
            "availability_reason": None,
            "provider": None,
            "dialect": None,
            "resolved_model": None,
            "endpoint_id": None,
            "endpoint_name": None,
            **_finalize_stats(key),
        }

        try:
            route = await registry.resolve_model_key(key)
            row["availability"] = True
            row["availability_reason"] = "ok"
            row["provider"] = route.provider
            row["dialect"] = route.dialect
            row["resolved_model"] = route.resolved_model
            row["endpoint_id"] = route.endpoint_id
            row["endpoint_name"] = route.endpoint.get("name")
            available += 1
        except Exception as exc:
            row["availability"] = False
            row["availability_reason"] = (str(exc) or type(exc).__name__)[:200]

        rows.append(row)

    total = len(keys)
    unavailable = max(total - available, 0)
    availability_rate = round((available / total) * 100.0, 2) if total > 0 else 0.0

    return {
        "time_window": time_window,
        "total": total,
        "available": available,
        "unavailable": unavailable,
        "availability_rate": availability_rate,
        "rows": rows,
    }


def _parse_e2e_mapped_model_run_row(row: dict[str, Any] | None, *, include_created_at: bool = False) -> dict[str, Any] | None:
    if not row:
        return None
    raw_results = row.get("results_json")
    results: list[dict[str, Any]] = []
    if isinstance(raw_results, str) and raw_results.strip():
        try:
            parsed = json.loads(raw_results)
            if isinstance(parsed, list):
                results = [item for item in parsed if isinstance(item, dict)]
        except Exception:
            results = []

    payload: dict[str, Any] = {
        "run_id": row.get("run_id"),
        "user_type": row.get("user_type"),
        "auth_mode": row.get("auth_mode"),
        "prompt_text": row.get("prompt_text"),
        "prompt_mode": row.get("prompt_mode"),
        "result_mode": row.get("result_mode"),
        "models_total": int(row.get("models_total") or 0),
        "models_success": int(row.get("models_success") or 0),
        "models_failed": int(row.get("models_failed") or 0),
        "started_at": row.get("started_at") or row.get("created_at"),
        "finished_at": row.get("finished_at"),
        "duration_ms": row.get("duration_ms"),
        "status": row.get("status"),
        "error_summary": row.get("error_summary"),
        "results": results,
    }
    if include_created_at:
        payload["created_at"] = row.get("created_at")
    return payload


@router.get("/stats/e2e-mapped-models")
async def get_e2e_mapped_models_stats(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取每日 E2E（映射模型可用性）最近结果。"""

    db = get_sqlite_manager(request.app)
    latest: dict[str, Any] = {}
    for user_type in ("anonymous", "permanent"):
        row = await db.fetchone(
            """
            SELECT *
            FROM e2e_mapped_model_runs
            WHERE user_type = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [user_type],
        )
        parsed = _parse_e2e_mapped_model_run_row(row)
        if parsed:
            latest[user_type] = parsed

    total_models = 0
    total_success = 0
    total_failed = 0
    for item in latest.values():
        if not isinstance(item, dict):
            continue
        total_models += int(item.get("models_total") or 0)
        total_success += int(item.get("models_success") or 0)
        total_failed += int(item.get("models_failed") or 0)

    summary = {
        "models_total": total_models,
        "models_success": total_success,
        "models_failed": total_failed,
        "success_rate": round((total_success / total_models) * 100.0, 2) if total_models > 0 else 0.0,
    }

    return {"code": 200, "data": {"latest": latest, "summary": summary}, "msg": "success"}


@router.get("/stats/e2e-mapped-model-runs")
async def get_e2e_mapped_model_runs(
    request: Request,
    user_type: str = Query("permanent", regex="^(anonymous|permanent)$", description="用户类型"),
    time_window: str = Query("24h", regex="^(24h|7d|30d)$", description="时间窗口"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, le=10000, description="偏移量（分页）"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 E2E（映射模型）运行记录列表（用于矩阵/回归观察）。"""

    now_utc = datetime.now(timezone.utc)
    if time_window == "30d":
        start_time = now_utc - timedelta(days=30)
    elif time_window == "7d":
        start_time = now_utc - timedelta(days=7)
    else:
        start_time = now_utc - timedelta(hours=24)

    start_ts = start_time.strftime("%Y-%m-%d %H:%M:%S")

    db = get_sqlite_manager(request.app)
    total_row = await db.fetchone(
        """
        SELECT COUNT(1) as total
        FROM e2e_mapped_model_runs
        WHERE user_type = ? AND created_at >= ?
        """,
        [user_type, start_ts],
    )
    total = int((total_row or {}).get("total") or 0)

    raw_rows = await db.fetchall(
        """
        SELECT *
        FROM e2e_mapped_model_runs
        WHERE user_type = ? AND created_at >= ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        [user_type, start_ts, int(limit), int(offset)],
    )

    runs: list[dict[str, Any]] = []
    for row in raw_rows:
        parsed = _parse_e2e_mapped_model_run_row(row, include_created_at=True)
        if parsed:
            runs.append(parsed)

    return {
        "code": 200,
        "data": {
            "user_type": user_type,
            "time_window": time_window,
            "limit": int(limit),
            "offset": int(offset),
            "total": total,
            "runs": runs,
        },
        "msg": "success",
    }


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
        日志列表（包装在统一响应格式中）
    """
    # 仅管理员可查看日志（简化实现，后续可扩展 RBAC）
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot access logs"},
        )

    log_collector: LogCollector = request.app.state.log_collector
    logs = log_collector.get_recent_logs(level=level, limit=limit)
    return {"code": 200, "data": {"level": level, "limit": limit, "count": len(logs), "logs": logs}, "msg": "success"}


@router.post("/logs/request")
async def create_request_raw_log(
    request: Request,
    payload: RequestRawLogIn,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """写入前端请求 raw 日志到 SQLite（由前端开关控制是否上报）。"""
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot write request logs"},
        )

    db = get_sqlite_manager(request.app)
    await db.log_request_raw(
        user_id=current_user.uid,
        request_id=payload.request_id,
        kind=payload.kind,
        method=payload.method,
        url=payload.url,
        status=payload.status,
        duration_ms=payload.duration_ms,
        request_raw=payload.request_raw,
        response_raw=payload.response_raw,
        error=payload.error,
    )

    return {"code": 200, "data": {"written": True}, "msg": "success"}


@router.get("/logs/request")
async def list_request_raw_logs(
    request: Request,
    limit: int = Query(200, ge=1, le=2000, description="最大返回条数"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """读取 SQLite 中的前端请求 raw 日志。"""
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot access request logs"},
        )

    db = get_sqlite_manager(request.app)
    items = await db.get_request_raw_logs(limit=limit)
    return {"code": 200, "data": {"count": len(items), "items": items}, "msg": "success"}


@router.delete("/logs/request")
async def clear_request_raw_logs(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """清空 SQLite 中的前端请求 raw 日志。"""
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot clear request logs"},
        )

    db = get_sqlite_manager(request.app)
    deleted = await db.clear_request_raw_logs()
    return {"code": 200, "data": {"deleted": deleted}, "msg": "success"}


# ============================================================================
# 配置管理端点
# ============================================================================


class DashboardConfig(BaseModel):
    """Dashboard 配置。"""

    websocket_push_interval: int = Field(10, ge=1, le=300, description="WebSocket 推送间隔（秒）")
    http_poll_interval: int = Field(30, ge=5, le=600, description="HTTP 轮询间隔（秒）")
    log_retention_size: int = Field(100, ge=10, le=1000, description="日志保留条数")
    e2e_interval_hours: Optional[int] = Field(
        24,
        ge=3,
        le=24,
        description="E2E 运行间隔（小时，3~24；配置后优先于 e2e_daily_time）",
    )
    e2e_daily_time: str = Field("05:00", description="每日 E2E 启动时间（HH:MM）", pattern=r"^\d{2}:\d{2}$")
    e2e_prompt_text: str = Field(
        "每日测试连通性和tools工具可用性",
        min_length=1,
        max_length=500,
        description="E2E 默认请求语句（可调整）",
    )


class DashboardConfigResponse(BaseModel):
    """Dashboard 配置响应。"""

    config: DashboardConfig = Field(..., description="当前配置")
    updated_at: Optional[str] = Field(None, description="最后更新时间")


async def _get_dashboard_config_payload(db: SQLiteManager) -> dict[str, Any]:
    default_config = DashboardConfig(
        websocket_push_interval=10,
        http_poll_interval=30,
        log_retention_size=100,
        e2e_interval_hours=24,
        e2e_daily_time="05:00",
        e2e_prompt_text="每日测试连通性和tools工具可用性",
    ).dict()

    row = await db.fetchone(
        "SELECT config_json, updated_at FROM dashboard_config WHERE id = 1",
        (),
    )
    updated_at = row.get("updated_at") if row else None
    merged = dict(default_config)
    if row:
        raw = row.get("config_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    merged.update(parsed)
            except Exception:
                pass

    try:
        validated = DashboardConfig(**merged)
    except Exception:
        validated = DashboardConfig(**default_config)
    return {"config": validated.dict(), "updated_at": updated_at}


@router.get("/stats/config")
async def get_dashboard_config(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取 Dashboard 配置。

    Args:
        request: FastAPI 请求对象
        current_user: 当前用户

    Returns:
        Dashboard 配置（包装在统一响应格式中）
    """
    db = get_sqlite_manager(request.app)
    config_data = await _get_dashboard_config_payload(db)
    return {"code": 200, "data": config_data, "msg": "success"}


@router.put("/stats/config")
async def update_dashboard_config(
    request: Request,
    config: DashboardConfig,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新 Dashboard 配置。

    Args:
        request: FastAPI 请求对象
        config: 新配置
        current_user: 当前用户

    Returns:
        更新后的配置（包装在统一响应格式中）
    """
    # 仅管理员可更新配置（简化实现，后续可扩展 RBAC）
    if current_user.user_type == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Anonymous users cannot update config"},
        )

    db = get_sqlite_manager(request.app)
    payload = config.dict()
    await db.execute(
        """
        INSERT INTO dashboard_config (id, config_json, updated_at)
        VALUES (1, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          config_json = excluded.config_json,
          updated_at = CURRENT_TIMESTAMP
        """,
        (json.dumps(payload, ensure_ascii=False),),
    )

    logger.info("Dashboard config updated by user_id=%s config=%s", current_user.uid, payload)

    config_data = await _get_dashboard_config_payload(db)
    return {"code": 200, "data": config_data, "msg": "success"}


# ============================================================================
# Request Tracing API
# ============================================================================


class TracingConfigResponse(BaseModel):
    enabled: bool


class TracingConfigRequest(BaseModel):
    enabled: bool


class ConversationLogsResponse(BaseModel):
    logs: list[dict]
    total: int


@router.get("/tracing/config", response_model=TracingConfigResponse)
async def get_tracing_config(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TracingConfigResponse:
    """获取请求追踪配置（仅 Dashboard 管理员）。"""
    if not is_dashboard_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅 Dashboard 管理员可访问"
        )

    db = get_sqlite_manager(request.app)
    enabled = await db.get_tracing_enabled()
    return TracingConfigResponse(enabled=enabled)


@router.post("/tracing/config", response_model=TracingConfigResponse)
async def set_tracing_config(
    payload: TracingConfigRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TracingConfigResponse:
    """设置请求追踪配置（仅 Dashboard 管理员）。"""
    if not is_dashboard_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅 Dashboard 管理员可访问"
        )

    db = get_sqlite_manager(request.app)
    await db.set_tracing_enabled(payload.enabled)
    return TracingConfigResponse(enabled=payload.enabled)


@router.get("/tracing/logs", response_model=ConversationLogsResponse)
async def get_conversation_logs(
    request: Request,
    limit: int = 50,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConversationLogsResponse:
    """获取最近的对话日志（仅 Dashboard 管理员，最多 50 条）。"""
    if not is_dashboard_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅 Dashboard 管理员可访问"
        )

    db = get_sqlite_manager(request.app)
    logs = await db.get_recent_conversation_logs(limit=min(limit, 50))
    return ConversationLogsResponse(logs=logs, total=len(logs))
