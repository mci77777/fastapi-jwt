"""健康探针端点 - 用于K8s/负载均衡器探活。"""
from fastapi import APIRouter
from app.settings.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    """
    健康检查端点 - 基础存活探针。
    
    返回200表示服务正在运行。
    """
    return {"status": "ok", "service": get_settings().app_name}


@router.get("/livez")
async def livez():
    """
    存活探针 - 检查服务是否存活。
    
    K8s使用此端点判断是否需要重启Pod。
    """
    return {"status": "alive", "service": get_settings().app_name}


@router.get("/readyz")
async def readyz():
    """
    就绪探针 - 检查服务是否准备好接收流量。
    
    K8s使用此端点判断是否将流量路由到此Pod。
    """
    # 简化实现：只要服务启动就认为就绪
    # 未来可以添加数据库连接检查、依赖服务检查等
    return {"status": "ready", "service": get_settings().app_name}

