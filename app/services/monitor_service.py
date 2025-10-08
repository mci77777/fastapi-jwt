"""Background scheduler for periodically checking AI endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.ai_config_service import AIConfigService

logger = logging.getLogger(__name__)


class EndpointMonitor:
    """Manage the lifecycle of the endpoint polling coroutine.

    The monitor:
    - accepts a polling interval between 10 and 600 seconds
    - delegates to ``AIConfigService.refresh_all_status`` every cycle
    - records the ISO timestamp of the last run and the last error message
    """

    def __init__(self, service: AIConfigService) -> None:
        self._service = service
        self._task: Optional[asyncio.Task[None]] = None
        self._interval: int = 60
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._last_run_iso: Optional[str] = None
        self._last_error: Optional[str] = None

    @property
    def interval(self) -> int:
        return self._interval

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, interval_seconds: int) -> None:
        """Start (or restart) the polling loop with the given interval."""

        if not 10 <= interval_seconds <= 600:
            raise ValueError("interval_out_of_range")

        async with self._lock:
            await self._stop_locked()
            self._interval = interval_seconds
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Endpoint monitor started interval=%s", interval_seconds)

    async def stop(self) -> None:
        """Stop the polling loop if it is currently running."""

        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        if self._task and not self._task.done():
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Endpoint monitor stopped")
        self._task = None

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self._run_once()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.debug("Endpoint monitor loop cancelled")
            raise

    async def _run_once(self) -> None:
        try:
            results = await self._service.refresh_all_status()
            if results:
                # refresh_all_status stores ISO timestamps itself; read the first item
                self._last_run_iso = results[0].get("last_checked_at")
            else:
                self._last_run_iso = None
            self._last_error = None
            logger.debug("Endpoint monitor refreshed %d endpoints", len(results))
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.exception("Endpoint monitor refresh failed")
            self._last_error = str(exc)

    def snapshot(self) -> dict[str, Optional[str | int | bool]]:
        """Return the current monitor status."""

        return {
            "is_running": self.is_running(),
            "interval_seconds": self._interval,
            "last_run_at": self._last_run_iso,
            "last_error": self._last_error,
        }
