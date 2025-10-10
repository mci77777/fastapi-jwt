"""JWT 对话模拟与压测服务。"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt

from app.services.ai_config_service import AIConfigService
from app.settings.config import Settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class JwtRunSummary:
    id: str
    prompt_id: int
    endpoint_id: int
    model: str | None
    batch_size: int
    concurrency: int
    stop_on_error: bool
    success_count: int
    failure_count: int
    status: str
    started_at: str
    finished_at: str
    errors: list[str]
    completed_count: int = 0  # 已完成数量(成功+失败)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "endpoint_id": self.endpoint_id,
            "model": self.model,
            "batch_size": self.batch_size,
            "concurrency": self.concurrency,
            "stop_on_error": self.stop_on_error,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "completed_count": self.completed_count,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "errors": self.errors,
        }


class JWTTestService:
    """封装 JWT 获取、单次对话模拟与批量压测逻辑。"""

    def __init__(self, ai_service: AIConfigService, settings: Settings, storage_dir: Path) -> None:
        self._ai_service = ai_service
        self._settings = settings
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._storage_dir / "jwt_runs.json"
        self._lock = asyncio.Lock()
        self._active_runs: dict[str, JwtRunSummary] = {}  # 运行中的压测状态

    async def simulate_dialog(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = payload.get("username") or "tester"
        token = self._generate_token(username)
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            result = await self._ai_service.test_prompt(
                prompt_id=payload["prompt_id"],
                endpoint_id=payload["endpoint_id"],
                message=self._decorate_message(payload["message"], run_id=None, index=0),
                model=payload.get("model"),
            )
        except RuntimeError as exc:
            error = str(exc)
        response = {
            "jwt_token": token,
            "result": result,
            "error": error,
        }
        return response

    async def run_load_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = uuid4().hex
        batch_size = int(payload.get("batch_size", 1))
        concurrency = max(1, min(int(payload.get("concurrency", 1)), batch_size))
        stop_on_error = bool(payload.get("stop_on_error", False))
        username = payload.get("username") or "load-test"
        token = self._generate_token(username)
        started_at = _utc_now()
        success_count = 0
        failure_count = 0
        errors: list[str] = []
        stop_event = asyncio.Event()
        queue: asyncio.Queue[int | None] = asyncio.Queue()

        # 初始化活动运行状态
        summary = JwtRunSummary(
            id=run_id,
            prompt_id=payload["prompt_id"],
            endpoint_id=payload["endpoint_id"],
            model=payload.get("model"),
            batch_size=batch_size,
            concurrency=concurrency,
            stop_on_error=stop_on_error,
            success_count=0,
            failure_count=0,
            completed_count=0,
            status="running",
            started_at=started_at,
            finished_at="",
            errors=[],
        )
        self._active_runs[run_id] = summary

        for idx in range(batch_size):
            queue.put_nowait(idx)
        for _ in range(concurrency):
            queue.put_nowait(None)

        semaphore = asyncio.Semaphore(concurrency)

        async def worker() -> None:
            nonlocal success_count, failure_count
            while True:
                idx = await queue.get()
                if idx is None:
                    queue.task_done()
                    break
                if stop_event.is_set():
                    queue.task_done()
                    continue
                message = self._decorate_message(payload["message"], run_id=run_id, index=idx)
                async with semaphore:
                    # 添加重试机制处理速率限制
                    max_retries = 3
                    base_delay = 1.0
                    last_error = None
                    for attempt in range(max_retries):
                        try:
                            # 在请求间添加小延迟以避免速率限制
                            if idx > 0:
                                await asyncio.sleep(0.1)
                            await self._ai_service.test_prompt(
                                prompt_id=payload["prompt_id"],
                                endpoint_id=payload["endpoint_id"],
                                message=message,
                                model=payload.get("model"),
                            )
                            success_count += 1
                            # 更新活动状态
                            if run_id in self._active_runs:
                                self._active_runs[run_id].success_count = success_count
                                self._active_runs[run_id].completed_count = success_count + failure_count
                            last_error = None
                            break
                        except RuntimeError as exc:
                            last_error = exc
                            error_msg = str(exc)
                            # 检查是否是速率限制错误
                            if "429" in error_msg and attempt < max_retries - 1:
                                # 指数退避重试
                                delay = base_delay * (2**attempt)
                                await asyncio.sleep(delay)
                                continue
                            # 其他错误或重试次数用尽
                            failure_count += 1
                            errors.append(f"[尝试 {attempt + 1}/{max_retries}] {error_msg}")
                            # 更新活动状态
                            if run_id in self._active_runs:
                                self._active_runs[run_id].failure_count = failure_count
                                self._active_runs[run_id].completed_count = success_count + failure_count
                                self._active_runs[run_id].errors = errors[:20]
                            if stop_on_error:
                                stop_event.set()
                            break
                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await queue.join()
        for task in workers:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finished_at = _utc_now()

        status = "success"
        if failure_count and success_count:
            status = "partial"
        elif failure_count and not success_count:
            status = "failed"

        summary.success_count = success_count
        summary.failure_count = failure_count
        summary.completed_count = success_count + failure_count
        summary.status = status
        summary.finished_at = finished_at
        summary.errors = errors[:20]

        # 从活动运行中移除
        self._active_runs.pop(run_id, None)

        await self._append_run(summary)
        tests = await self._ai_service.list_prompt_tests_by_run(run_id, limit=batch_size)
        return {
            "jwt_token": token,
            "summary": summary.to_dict(),
            "tests": tests,
        }

    async def get_run(self, run_id: str) -> dict[str, Any]:
        # 优先检查活动运行
        if run_id in self._active_runs:
            active_summary = self._active_runs[run_id]
            # 获取当前已完成的测试记录
            tests = await self._ai_service.list_prompt_tests_by_run(run_id, limit=1000)
            return {
                "summary": active_summary.to_dict(),
                "tests": tests,
                "is_running": True,
            }

        # 查询已完成的运行
        runs = await self._read_runs()
        run = next((item for item in runs if item["id"] == run_id), None)
        if not run:
            return {}
        tests = await self._ai_service.list_prompt_tests_by_run(run_id, limit=1000)
        return {
            "summary": run,
            "tests": tests,
            "is_running": False,
        }

    def _generate_token(self, username: str) -> str:
        now = int(datetime.now(timezone.utc).timestamp())
        issuer = str(self._settings.supabase_issuer) if self._settings.supabase_issuer else "http://localhost:9999"
        payload = {
            "iss": issuer,
            "sub": f"test-user-{username}",
            "aud": "authenticated",
            "exp": now + 3600,
            "iat": now,
            "email": f"{username}@test.local",
            "role": "authenticated",
            "is_anonymous": False,
            "user_metadata": {
                "username": username,
                "is_admin": username == "admin",
            },
            "app_metadata": {
                "provider": "test",
                "providers": ["test"],
            },
        }
        return jwt.encode(payload, self._settings.supabase_jwt_secret, algorithm="HS256")

    def _decorate_message(self, message: str, *, run_id: str | None, index: int) -> str:
        base = message or ""
        suffix = ""
        if run_id:
            suffix = f"\n[run_id={run_id} index={index}]"
        return f"{base}{suffix}"

    async def _append_run(self, summary: JwtRunSummary) -> None:
        async with self._lock:
            runs = await self._read_runs()
            runs.insert(0, summary.to_dict())
            # 保留最近 200 条
            if len(runs) > 200:
                runs = runs[:200]
            await self._write_runs(runs)

    async def _read_runs(self) -> list[dict[str, Any]]:
        if not self._file_path.exists():
            return []
        text = await asyncio.to_thread(self._file_path.read_text, encoding="utf-8")
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return payload
        except json.JSONDecodeError:
            pass
        return []

    async def _write_runs(self, runs: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(
            self._file_path.write_text,
            json.dumps(runs, ensure_ascii=False, indent=2),
            "utf-8",
        )


__all__ = ["JWTTestService"]
