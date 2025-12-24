"""Supabase 保活服务 - 防止免费层实例因 7 天无活动而暂停。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.settings.config import Settings

logger = logging.getLogger(__name__)


class SupabaseKeepaliveService:
    """定期向 Supabase REST API 发送轻量级请求以保持实例活跃。

    Supabase 免费层项目在 7 天无活动后会自动暂停。
    此服务通过定期发送 HEAD 请求到 REST API 来防止暂停。

    推荐间隔：5-10 分钟（默认 10 分钟）
    """

    def __init__(self, settings: Settings) -> None:
        """初始化保活服务。

        Args:
            settings: 应用配置对象
        """
        self._settings = settings
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._last_ping_iso: Optional[str] = None
        self._last_error: Optional[str] = None
        self._success_count: int = 0
        self._failure_count: int = 0

    @property
    def is_enabled(self) -> bool:
        """检查保活功能是否启用。"""
        return (
            self._settings.supabase_keepalive_enabled
            and bool(self._settings.supabase_project_id)
            and bool(self._settings.supabase_service_role_key)
        )

    @property
    def interval_seconds(self) -> int:
        """获取保活间隔（秒）。"""
        return self._settings.supabase_keepalive_interval_minutes * 60

    def is_running(self) -> bool:
        """检查保活任务是否正在运行。"""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """启动保活任务。"""
        if not self.is_enabled:
            logger.info("Supabase keepalive is disabled or not configured")
            return

        async with self._lock:
            if self.is_running():
                logger.warning("Supabase keepalive is already running")
                return

            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run_loop())
            logger.info(
                "Supabase keepalive started (interval=%d seconds, project_id=%s)",
                self.interval_seconds,
                self._settings.supabase_project_id,
            )

    async def stop(self) -> None:
        """停止保活任务。"""
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        """内部停止逻辑（需持有锁）。"""
        if self._task and not self._task.done():
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Supabase keepalive stopped")
        self._task = None

    async def _run_loop(self) -> None:
        """保活任务主循环。"""
        try:
            while not self._stop_event.is_set():
                await self._ping_once()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.debug("Supabase keepalive loop cancelled")
            raise

    async def _ping_once(self) -> None:
        """执行一次保活 ping。"""
        if not self._settings.supabase_project_id or not self._settings.supabase_service_role_key:
            logger.error("Supabase keepalive: missing project_id or service_role_key")
            return

        base_url = f"https://{self._settings.supabase_project_id}.supabase.co/rest/v1"
        headers = {
            "apikey": self._settings.supabase_service_role_key,
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
        }

        # 重试配置
        max_retries = 3
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
                    # 使用 HEAD 请求到 /ai_model 表（与 supabase_status 一致，轻量级查询）
                    response = await client.head(f"{base_url}/ai_model", headers=headers, params={"limit": 1})
                    response.raise_for_status()

                # 成功处理
                self._last_ping_iso = datetime.now(timezone.utc).isoformat()
                self._success_count += 1
                self._last_error = None
                
                # 仅在重试后成功时记录 INFO，否则 DEBUG
                if attempt > 1:
                    logger.info("Supabase keepalive ping successful after %d attempts", attempt)
                else:
                    logger.debug("Supabase keepalive ping successful")

                # 更新 Prometheus 指标
                from app.core.metrics import supabase_keepalive_last_success_timestamp, supabase_keepalive_requests_total

                supabase_keepalive_requests_total.labels(status="success").inc()
                supabase_keepalive_last_success_timestamp.set_to_current_time()
                return

            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < max_retries:
                    await asyncio.sleep(1)  # 简单的指数退避或固定等待
                    continue
            except Exception as exc:  # pragma: no cover
                # 非网络/HTTP 错误不重试，直接记录
                self._failure_count += 1
                self._last_error = str(exc)
                logger.exception("Supabase keepalive ping unexpected error (total_failures=%d)", self._failure_count)
                
                from app.core.metrics import supabase_keepalive_requests_total
                supabase_keepalive_requests_total.labels(status="failure").inc()
                return

        # 重试全部失败后记录警告
        self._failure_count += 1
        error_msg = f"{type(last_exc).__name__}: {last_exc}"
        self._last_error = error_msg
        
        logger.warning(
            "Supabase keepalive ping failed (attempts=%d, total_failures=%d): %s",
            max_retries,
            self._failure_count,
            error_msg,
        )

        # 更新 Prometheus 指标
        from app.core.metrics import supabase_keepalive_requests_total

        supabase_keepalive_requests_total.labels(status="failure").inc()

    def snapshot(self) -> dict[str, Optional[str | int | bool]]:
        """返回当前保活服务状态快照。"""
        return {
            "enabled": self.is_enabled,
            "is_running": self.is_running(),
            "interval_seconds": self.interval_seconds,
            "last_ping_at": self._last_ping_iso,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "last_error": self._last_error,
        }
