"""Multi-Agent WebSocket 端点。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import HTTPException

from app.auth import AuthenticatedUser
from app.auth.jwt_verifier import get_jwt_verifier
from app.log import logger

router = APIRouter(tags=["agents"])

# 模块级连接池（简化实现，避免引入新服务层）
_active_connections: Dict[str, WebSocket] = {}


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
        logger.info("WebSocket JWT verification success: uid=%s user_type=%s", user.uid, user.user_type)
        return user
    except HTTPException as exc:
        logger.warning(
            "WebSocket JWT verification failed: HTTPException status=%s detail=%s", exc.status_code, exc.detail
        )
        raise
    except Exception as exc:
        logger.error("WebSocket JWT verification failed: unexpected error=%s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid token"},
        )


@router.websocket("/agents")
async def agents_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token"),
) -> None:
    """Multi-Agent WebSocket 端点，支持实时对话。

    Args:
        websocket: WebSocket 连接
        token: JWT token（查询参数）

    连接流程:
        1. 接受连接
        2. JWT 验证
        3. 检查用户类型（匿名用户禁止访问）
        4. 注册到连接池
        5. 处理双向消息（客户端 ↔ 服务器 ↔ AI Agent）
        6. 断线时清理连接

    消息格式:
        客户端 → 服务器:
        {
            "type": "message",
            "content": "用户消息内容",
            "agent_id": "agent_name"  // 可选，指定 Agent
        }

        服务器 → 客户端:
        {
            "type": "response",
            "content": "AI 回复内容",
            "agent_id": "agent_name",
            "timestamp": "2025-10-14T12:00:00Z"
        }
    """
    # 先接受连接（必须在任何操作之前）
    await websocket.accept()
    logger.info("WebSocket connection accepted for /agents endpoint")

    # JWT 验证
    try:
        user = await get_current_user_ws(token)
        logger.info("JWT verification success: uid=%s, user_type=%s", user.uid, user.user_type)
    except HTTPException as exc:
        logger.warning("JWT verification failed (HTTPException): status=%s, detail=%s", exc.status_code, exc.detail)
        await websocket.close(code=1008, reason="Unauthorized")
        logger.warning("WebSocket connection rejected: unauthorized")
        return
    except Exception as exc:
        logger.error("JWT verification failed (Exception): %s", exc, exc_info=True)
        await websocket.close(code=1011, reason="Internal server error")
        return

    # 检查用户类型（匿名用户禁止访问）
    if user.user_type == "anonymous":
        logger.warning("WebSocket connection rejected: anonymous user uid=%s", user.uid)
        await websocket.close(code=1008, reason="Anonymous users not allowed")
        return

    logger.info("WebSocket connection fully accepted: uid=%s, user_type=%s", user.uid, user.user_type)

    # 注册连接到连接池
    connection_id = f"{user.uid}_{datetime.utcnow().timestamp()}"
    _active_connections[connection_id] = websocket
    logger.info(
        "Agent connection registered: connection_id=%s total_connections=%d", connection_id, len(_active_connections)
    )

    try:
        # 发送欢迎消息
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Connected to Multi-Agent WebSocket",
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # 消息循环
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            logger.debug("Received message from client: connection_id=%s data=%s", connection_id, data)

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid JSON format",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                continue

            # 处理消息
            if message.get("type") == "message":
                content = message.get("content", "")
                agent_id = message.get("agent_id", "default")

                # TODO: 集成 AI Agent 处理逻辑
                # 当前简化实现：直接回显消息
                response_content = f"Echo from Agent '{agent_id}': {content}"

                await websocket.send_json(
                    {
                        "type": "response",
                        "content": response_content,
                        "agent_id": agent_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                logger.info("Sent response to client: connection_id=%s agent_id=%s", connection_id, agent_id)

            elif message.get("type") == "ping":
                # 心跳响应
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message.get('type')}",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed: connection_id=%s", connection_id)
    except Exception as exc:
        logger.exception("WebSocket error: connection_id=%s error=%s", connection_id, exc)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        # 确保无论如何都清理连接
        if connection_id in _active_connections:
            del _active_connections[connection_id]
            logger.info(
                "Agent connection removed: connection_id=%s remaining_connections=%d",
                connection_id,
                len(_active_connections),
            )


def get_active_connections_count() -> int:
    """获取当前活跃连接数（用于监控）。"""
    return len(_active_connections)
