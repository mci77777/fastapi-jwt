"""Prometheus指标导出端点。"""
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    """
    Prometheus指标导出端点。
    
    返回Prometheus格式的指标数据，供Grafana等监控系统抓取。
    
    指标包括：
    - auth_requests_total: 认证请求总数（按状态和用户类型）
    - auth_request_duration_seconds: 认证请求持续时间
    - jwt_validation_errors_total: JWT验证错误总数
    - jwks_cache_hits_total: JWKS缓存命中总数
    - active_connections: 活跃连接数
    - rate_limit_blocks_total: 限流阻止总数
    """
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

