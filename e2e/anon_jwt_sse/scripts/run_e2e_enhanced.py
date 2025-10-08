#!/usr/bin/env python3
"""
匿名用户端到端流程：
1. 调用 Supabase 邮箱注册 API 创建测试账号
2. 使用注册信息登录换取 JWT
3. 携带 JWT 调用 AI 消息接口发送 “hello”
4. 订阅 SSE 事件直到收到 [DONE]
5. 把链路中的请求、响应、事件统一记录到 JSON
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DEFAULT_OUTPUT = ARTIFACTS_DIR / "anon_e2e_trace.json"


@dataclass
class StepRecord:
    name: str
    success: bool
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class TraceReport:
    started_at: float
    finished_at: Optional[float] = None
    supabase_project_id: Optional[str] = None
    supabase_url: Optional[str] = None
    api_base_url: str = "http://localhost:9999/api/v1"
    user_email: str = ""
    user_password: str = ""
    steps: List[StepRecord] = field(default_factory=list)

    def add_step(self, step: StepRecord) -> None:
        self.steps.append(step)

    def to_json(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": (self.finished_at or time.time()) - self.started_at,
            "supabase_project_id": self.supabase_project_id,
            "supabase_url": self.supabase_url,
            "api_base_url": self.api_base_url,
            "user_email": self.user_email,
            "steps": [asdict(step) for step in self.steps],
        }


class AnonymousE2E:
    """执行匿名用户完整链路并产出 JSON 记录。"""

    def __init__(
        self,
        api_base_url: str,
        supabase_url: str,
        supabase_service_key: str,
        supabase_anon_key: str,
        output_path: Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_service_key = supabase_service_key
        self.supabase_anon_key = supabase_anon_key
        self.output_path = output_path
        self.timeout = timeout
        self.report = TraceReport(
            started_at=time.time(),
            supabase_project_id=os.getenv("SUPABASE_PROJECT_ID"),
            supabase_url=self.supabase_url,
            api_base_url=self.api_base_url,
        )

    @staticmethod
    def _now_ms() -> float:
        return time.perf_counter() * 1000

    async def _register_user(self, client: httpx.AsyncClient, email: str, password: str) -> StepRecord:
        url = f"{self.supabase_url}/auth/v1/signup"
        payload = {
            "email": email,
            "password": password,
            "data": {
                "source": "anon-e2e",
                "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }
        headers = {
            "apikey": self.supabase_service_key or self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_service_key or self.supabase_anon_key}",
            "Content-Type": "application/json",
        }

        start = self._now_ms()
        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout)
        duration = self._now_ms() - start

        success = resp.status_code in (200, 201, 202, 400)
        notes: Dict[str, Any] = {}
        if resp.status_code == 400:
            notes["info"] = "用户可能已存在，继续使用现有账号"

        return StepRecord(
            name="supabase_signup",
            success=success,
            request={"url": url, "payload": payload},
            response={"status_code": resp.status_code, "body": _safe_json(resp)},
            notes=notes,
            duration_ms=duration,
        )

    async def _login_user(self, client: httpx.AsyncClient, email: str, password: str) -> StepRecord:
        url = f"{self.supabase_url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}
        headers = {
            "apikey": self.supabase_service_key or self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_service_key or self.supabase_anon_key}",
            "Content-Type": "application/json",
        }

        start = self._now_ms()
        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout)
        duration = self._now_ms() - start

        body = _safe_json(resp)
        token = body.get("access_token") if isinstance(body, dict) else None

        return StepRecord(
            name="supabase_login",
            success=resp.status_code == 200 and isinstance(token, str),
            request={"url": url, "payload": payload},
            response={"status_code": resp.status_code, "body": body},
            notes={"access_token_preview": f"{token[:12]}..." if token else None},
            duration_ms=duration,
        )

    async def _send_message(self, client: httpx.AsyncClient, token: str) -> StepRecord:
        url = f"{self.api_base_url}/messages"
        payload = {
            "text": "hello",
            "conversation_id": None,
            "metadata": {
                "source": "anon_e2e",
                "trace_id": str(uuid.uuid4()),
            },
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Trace-Id": payload["metadata"]["trace_id"],
        }

        start = self._now_ms()
        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout)
        duration = self._now_ms() - start

        body = _safe_json(resp)
        message_id = body.get("message_id") if isinstance(body, dict) else None

        return StepRecord(
            name="api_create_message",
            success=resp.status_code in (200, 202) and isinstance(message_id, str),
            request={"url": url, "payload": payload},
            response={"status_code": resp.status_code, "body": body},
            notes={"message_id": message_id},
            duration_ms=duration,
        )

    async def _stream_events(self, client: httpx.AsyncClient, token: str, message_id: str) -> StepRecord:
        url = f"{self.api_base_url}/messages/{message_id}/events"
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}

        events: List[Dict[str, Any]] = []
        status_code = None
        start = self._now_ms()

        try:
            async with client.stream("GET", url, headers=headers, timeout=None) as resp:
                status_code = resp.status_code

                if resp.status_code != 200:
                    text = await resp.aread()
                    return StepRecord(
                        name="api_stream_events",
                        success=False,
                        request={"url": url},
                        response={"status_code": resp.status_code, "body": text.decode("utf-8", "ignore")},
                        duration_ms=self._now_ms() - start,
                    )

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            events.append({"event": "done"})
                            break
                        events.append({"event": "data", "payload": _safe_parse_json(data_str)})
        except Exception as exc:  # pragma: no cover
            return StepRecord(
                name="api_stream_events",
                success=False,
                request={"url": url},
                response={"status_code": status_code, "body": str(exc)},
                duration_ms=self._now_ms() - start,
                notes={"error": str(exc)},
            )

        duration = self._now_ms() - start
        return StepRecord(
            name="api_stream_events",
            success=len(events) > 0 and events[-1].get("event") == "done",
            request={"url": url},
            response={"status_code": status_code, "events": events},
            duration_ms=duration,
        )

    async def run(self) -> int:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

        email = f"anon_e2e_{int(time.time())}@test.local"
        password = f"Pwd-{uuid.uuid4().hex[:12]}"
        self.report.user_email = email
        self.report.user_password = password

        print(f"[INFO] Starting anonymous E2E test; target API: {self.api_base_url}")
        print(f"[INFO] Using temporary email: {email}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 注册
            signup_step = await self._register_user(client, email, password)
            self.report.add_step(signup_step)
            print(f"[STEP] Signup status: {signup_step.response['status_code']}")
            if not signup_step.success:
                return await self._finalize(1)

            # 登录换取 JWT
            login_step = await self._login_user(client, email, password)
            self.report.add_step(login_step)
            print(f"[STEP] Login status: {login_step.response['status_code']}")
            if not login_step.success:
                return await self._finalize(1)

            token = login_step.response["body"]["access_token"]  # type: ignore[index]

            # 发送消息
            message_step = await self._send_message(client, token)
            self.report.add_step(message_step)
            print(f"[STEP] Message status: {message_step.response['status_code']}")
            if not message_step.success:
                return await self._finalize(1)

            message_id = message_step.notes.get("message_id")
            if not message_id:
                return await self._finalize(1)

            # 监听 SSE
            events_step = await self._stream_events(client, token, message_id)
            self.report.add_step(events_step)
            print(f"[STEP] SSE status: {events_step.response.get('status_code')}")
            if not events_step.success:
                return await self._finalize(1)

        return await self._finalize(0)

    async def _finalize(self, exit_code: int) -> int:
        self.report.finished_at = time.time()
        with self.output_path.open("w", encoding="utf-8") as fp:
            json.dump(self.report.to_json(), fp, ensure_ascii=False, indent=2)
        print(f"[INFO] Full trace saved to: {self.output_path}")
        return exit_code


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _safe_parse_json(data: str) -> Any:
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data


def load_env() -> None:
    # 尝试加载多种位置的 .env，顺序：项目根 -> e2e/.env.local
    env_files = [
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[1] / ".env.local",
    ]
    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file, override=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="匿名 JWT E2E 测试")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", "http://localhost:9999/api/v1"),
        help="后端 API 基础地址，默认为 http://localhost:9999/api/v1",
    )
    parser.add_argument(
        "--supabase-url",
        default=os.getenv("SUPABASE_URL"),
        help="Supabase 项目地址，如 https://xxx.supabase.co",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"链路 JSON 输出路径，默认 {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("E2E_HTTP_TIMEOUT", "30")),
        help="HTTP 请求超时时间（秒），默认为 30",
    )
    return parser.parse_args()


async def async_main() -> int:
    load_env()
    args = parse_args()

    supabase_url = args.supabase_url or os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    anon_key = os.getenv("SUPABASE_ANON_KEY") or ""

    missing = [name for name, value in [
        ("SUPABASE_URL", supabase_url),
        ("SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY", service_key or anon_key),
    ] if not value]

    if missing:
        print("ERROR: 缺少必要的 Supabase 配置：", ", ".join(missing))
        return 1

    runner = AnonymousE2E(
        api_base_url=args.api_base_url,
        supabase_url=supabase_url,
        supabase_service_key=service_key,
        supabase_anon_key=anon_key,
        output_path=Path(args.output),
        timeout=args.timeout,
    )
    return await runner.run()


def main() -> None:
    exit_code = asyncio.run(async_main())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

