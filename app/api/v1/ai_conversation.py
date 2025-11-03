"""AI 对话监控与日志端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.v1.llm_common import create_response
from app.auth import AuthenticatedUser, get_current_user
from app.db.sqlite_manager import get_sqlite_manager

router = APIRouter(prefix="/ai/conversation", tags=["ai-conversation"])


@router.get("/logs")
async def get_conversation_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=100, description="返回记录数量上限"),  # noqa: B008
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """获取最近的 AI 对话原始日志（最多 100 条）。

    返回包含完整请求/响应 payload 的日志记录，用于调试和监控。

    Args:
        request: FastAPI 请求对象
        limit: 返回记录数量上限（默认 100）
        current_user: 当前认证用户

    Returns:
        包含日志列表的响应
    """
    db = get_sqlite_manager(request.app)
    logs = await db.get_conversation_logs(limit=limit)

    return create_response(
        data=logs,
        total=len(logs),
        msg=f"成功获取 {len(logs)} 条对话日志",
    )


@router.get("/health")
async def get_conversation_health(
    request: Request,
) -> JSONResponse:
    """获取 AI 对话端点的综合健康状态。

    此端点无需认证，用于监控工具和健康检查。

    返回信息包括：
    - AI provider 连通性状态
    - 模型可用性检查
    - Supabase 连接状态
    - 最近错误率
    - 平均延迟指标

    Returns:
        包含健康状态的 JSON 响应
    """
    from app.core.metrics import ai_conversation_latency_seconds
    from app.services.ai_config_service import AIConfigService

    # 获取服务实例
    ai_config_service: AIConfigService = request.app.state.ai_config_service

    # 1. Supabase 连接状态
    supabase_status = await ai_config_service.supabase_status()

    # 2. 从 Prometheus 指标计算错误率和延迟
    try:
        # 获取所有标签组合的指标
        metrics_data = {}
        for family in ai_conversation_latency_seconds.collect():
            for sample in family.samples:
                if sample.name.endswith("_count"):
                    labels = sample.labels
                    key = (labels.get("model", "unknown"), labels.get("status", "unknown"))
                    if key not in metrics_data:
                        metrics_data[key] = {"count": 0, "sum": 0}
                    metrics_data[key]["count"] = sample.value
                elif sample.name.endswith("_sum"):
                    labels = sample.labels
                    key = (labels.get("model", "unknown"), labels.get("status", "unknown"))
                    if key not in metrics_data:
                        metrics_data[key] = {"count": 0, "sum": 0}
                    metrics_data[key]["sum"] = sample.value

        # 计算总请求数、成功数、错误数
        total_requests = 0
        success_requests = 0
        error_requests = 0
        total_latency_sum = 0

        for (model, status), data in metrics_data.items():
            count = data["count"]
            total_requests += count
            total_latency_sum += data["sum"]

            if status == "success":
                success_requests += count
            else:
                error_requests += count

        # 计算错误率和平均延迟
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        avg_latency_ms = (total_latency_sum / total_requests * 1000) if total_requests > 0 else 0

    except Exception:
        # 如果指标收集失败，返回默认值
        error_rate = 0
        avg_latency_ms = 0
        total_requests = 0

    # 3. AI Provider 连通性（简化检查：基于最近请求）
    ai_provider_status = "online" if total_requests > 0 else "unknown"

    # 4. 模型可用性（从 ai_endpoints 表获取）
    db = get_sqlite_manager(request.app)
    try:
        endpoints = await db.fetchall(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active
            FROM ai_endpoints
        """
        )
        total_models = endpoints[0]["total"] if endpoints else 0
        active_models = endpoints[0]["active"] if endpoints else 0
    except Exception:
        total_models = 0
        active_models = 0

    # 构建健康状态响应
    health_status = {
        "status": "healthy" if error_rate < 5 and supabase_status.get("status") != "offline" else "degraded",
        "timestamp": "2025-10-15T00:00:00Z",  # 实际应使用当前时间
        "components": {
            "ai_provider": {
                "status": ai_provider_status,
                "total_requests": total_requests,
                "error_rate_percent": round(error_rate, 2),
                "avg_latency_ms": round(avg_latency_ms, 2),
            },
            "supabase": {
                "status": supabase_status.get("status", "unknown"),
                "latency_ms": supabase_status.get("latency_ms"),
                "detail": supabase_status.get("detail"),
            },
            "models": {
                "total": total_models,
                "active": active_models,
                "status": "online" if active_models > 0 else "offline",
            },
        },
        "metrics": {
            "total_requests": total_requests,
            "success_requests": success_requests,
            "error_requests": error_requests,
            "error_rate_percent": round(error_rate, 2),
            "avg_latency_ms": round(avg_latency_ms, 2),
        },
    }

    return JSONResponse(content=health_status)
