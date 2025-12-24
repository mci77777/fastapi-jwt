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
import html
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

try:
    from mail_api_client import MailApiClient, Mailbox  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    from .mail_api_client import MailApiClient, Mailbox  # type: ignore[import-not-found]

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
        self.mail_api: Optional[MailApiClient] = None
        self.report = TraceReport(
            started_at=time.time(),
            supabase_project_id=os.getenv("SUPABASE_PROJECT_ID"),
            supabase_url=self.supabase_url,
            api_base_url=self.api_base_url,
        )

    @staticmethod
    def _now_ms() -> float:
        return time.perf_counter() * 1000

    @staticmethod
    def _redact_password(payload: Dict[str, Any]) -> Dict[str, Any]:
        redacted = dict(payload)
        if "password" in redacted:
            redacted["password"] = "<redacted>"
        return redacted

    @staticmethod
    def _redact_tokens(body: Any) -> Any:
        if not isinstance(body, dict):
            return body
        redacted = dict(body)
        for key in (
            "access_token",
            "refresh_token",
            "provider_token",
            "provider_refresh_token",
            "token",
        ):
            if key in redacted:
                redacted[key] = "<redacted>"
        return redacted

    @staticmethod
    def _extract_otp(text: str) -> Optional[str]:
        """
        提取 6 位验证码（优先匹配带关键词的形式，避免误命中无关数字）。
        """
        if not text:
            return None
        patterns = [
            r"(?:验证码|驗證碼|verification code|verify code|one[- ]time code|otp|code)\s*[:：]?\s*([0-9]{6})",
            r"(?:验证码|驗證碼|verification code|otp|code)\s*([0-9]{6})\b",
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        # 兜底：仅当邮件文本包含明显“验证”语义时才允许匹配任意 6 位数字
        if re.search(r"(confirm|verify|verification|signup|注册|验证|驗證)", text, flags=re.IGNORECASE):
            m = re.search(r"\b([0-9]{6})\b", text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _normalize_messages_list(data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [m for m in data if isinstance(m, dict)]
        if not isinstance(data, dict):
            return []
        for key in ("messages", "data", "items", "list"):
            v = data.get(key)
            if isinstance(v, list):
                return [m for m in v if isinstance(m, dict)]
        return []

    @staticmethod
    def _extract_message_id(message: Dict[str, Any]) -> Optional[str]:
        for key in ("messageId", "message_id", "id"):
            v = message.get(key)
            if isinstance(v, str) and v.strip():
                return v
        return None

    @staticmethod
    def _extract_text_from_message(msg: Dict[str, Any]) -> str:
        for key in ("text", "body", "content", "raw", "html"):
            v = msg.get(key)
            if isinstance(v, str) and v.strip():
                return v
        data = msg.get("data")
        if isinstance(data, dict):
            for key in ("text", "body", "content", "html"):
                v = data.get(key)
                if isinstance(v, str) and v.strip():
                    return v
        return ""

    @staticmethod
    def _is_domain_like(value: str) -> bool:
        v = value.strip().lower()
        if not v or " " in v or "@" in v or "/" in v:
            return False
        return bool(re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", v))

    @classmethod
    def _collect_domain_candidates(cls, obj: Any, out: set[str]) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                cls._collect_domain_candidates(v, out)
            return
        if isinstance(obj, list):
            for v in obj:
                cls._collect_domain_candidates(v, out)
            return
        if isinstance(obj, str) and cls._is_domain_like(obj):
            out.add(obj.strip())
            return
        if isinstance(obj, str) and "," in obj:
            for part in obj.split(","):
                if cls._is_domain_like(part):
                    out.add(part.strip())

    @classmethod
    def _collect_strings(cls, obj: Any, out: list[str], *, max_items: int = 200, max_len: int = 8000) -> None:
        if len(out) >= max_items:
            return
        if isinstance(obj, dict):
            for v in obj.values():
                cls._collect_strings(v, out, max_items=max_items, max_len=max_len)
            return
        if isinstance(obj, list):
            for v in obj:
                cls._collect_strings(v, out, max_items=max_items, max_len=max_len)
            return
        if isinstance(obj, str):
            s = obj.strip()
            if not s:
                return
            if len(s) > max_len:
                s = s[:max_len] + "…"
            out.append(s)

    def _is_email_not_confirmed(self, body: Any) -> bool:
        if isinstance(body, dict):
            msg = body.get("msg") or body.get("message") or ""
            err = body.get("error") or ""
            code = body.get("error_code") or body.get("code") or ""
            text = " ".join([str(msg), str(err), str(code)])
        else:
            text = str(body)
        text = text.lower()
        return ("not confirmed" in text) or ("email_not_confirmed" in text) or ("email not confirmed" in text)

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
            request={"url": url, "payload": self._redact_password(payload)},
            response={"status_code": resp.status_code, "body": self._redact_tokens(_safe_json(resp))},
            notes=notes,
            duration_ms=duration,
        )

    async def _login_user(self, client: httpx.AsyncClient, email: str, password: str) -> tuple[StepRecord, Optional[str]]:
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

        step = StepRecord(
            name="supabase_login",
            success=resp.status_code == 200 and isinstance(token, str),
            request={"url": url, "payload": self._redact_password(payload)},
            response={"status_code": resp.status_code, "body": self._redact_tokens(body)},
            notes={"access_token_len": len(token) if isinstance(token, str) else None},
            duration_ms=duration,
        )
        return step, (token if isinstance(token, str) else None)

    async def _confirm_email_via_mail_api(
        self,
        client: httpx.AsyncClient,
        *,
        mailbox: Mailbox,
        max_wait_seconds: float,
        poll_interval_seconds: float,
        otp_output_path: Optional[str],
    ) -> StepRecord:
        if not self.mail_api:
            return StepRecord(name="supabase_confirm_email", success=False, notes={"error": "mail_api_not_configured"})

        start = self._now_ms()
        deadline = time.monotonic() + max_wait_seconds
        checked = 0
        last_error: Optional[str] = None
        last_message_id: Optional[str] = None
        last_subject: Optional[str] = None
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=self.timeout) as mail_client:
            while time.monotonic() < deadline:
                try:
                    inbox = await self.mail_api.list_messages(mail_client, mailbox_id=mailbox.mailbox_id)
                    if isinstance(inbox, dict) and inbox.get("error"):
                        last_error = f"list_messages_failed: {inbox.get('error')}"
                        await asyncio.sleep(poll_interval_seconds)
                        continue
                    messages = self._normalize_messages_list(inbox)

                    for m in messages:
                        mid = self._extract_message_id(m)
                        if not mid or mid in seen:
                            continue
                        seen.add(mid)
                        checked += 1
                        last_message_id = mid

                        detail = await self.mail_api.get_message(
                            mail_client, mailbox_id=mailbox.mailbox_id, message_id=mid
                        )
                        if isinstance(detail, dict) and detail.get("error"):
                            last_error = f"get_message_failed: {detail.get('error')}"
                            continue
                        subject = detail.get("subject") or (detail.get("data") or {}).get("subject")  # type: ignore[union-attr]
                        last_subject = subject if isinstance(subject, str) else None

                        text = self._extract_text_from_message(detail)
                        if not text:
                            candidates: list[str] = []
                            self._collect_strings(detail, candidates)
                            text = "\n".join(candidates)
                        text = html.unescape(text or "")

                        # 允许把 OTP 导出给人工验证（不写入 trace/artifacts）
                        otp = self._extract_otp(text)
                        if otp_output_path and otp:
                            try:
                                Path(otp_output_path).write_text(f"email={mailbox.email}\notp={otp}\n", encoding="utf-8")
                            except Exception:
                                pass

                        urls = re.findall(r"https?://[^\s\"'<>]+", text)
                        confirm_url = None
                        for u in urls:
                            if "/auth/v1/verify" in u:
                                confirm_url = u
                                break

                        if confirm_url:
                            # 不把 token 写进 artifacts：只记录 base（去掉 query）
                            safe_url_base = confirm_url.split("?", 1)[0]
                            # 只需触发 verify；不要跟随 redirect_to（可能指向本地或不可达域名）
                            r = await client.get(confirm_url, follow_redirects=False, timeout=self.timeout)
                            duration = self._now_ms() - start
                            if otp_output_path:
                                try:
                                    meta_path = Path(otp_output_path).with_name("mail_meta.json")
                                    meta = {
                                        "email": mailbox.email,
                                        "mailbox_id": mailbox.mailbox_id,
                                        "message_id": mid,
                                        "subject": subject,
                                        "verify_url_base": safe_url_base,
                                        "has_otp": bool(otp),
                                        "otp_len": (len(otp) if otp else None),
                                    }
                                    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                                except Exception:
                                    pass
                            return StepRecord(
                                name="supabase_confirm_email",
                                success=r.status_code in (200, 204, 302, 303, 307, 308),
                                request={"url": safe_url_base, "mailbox_id": mailbox.mailbox_id},
                                response={"status_code": r.status_code},
                                notes={
                                    "method": "link",
                                    "message_id": mid,
                                    "subject": subject,
                                    "checked_messages": checked,
                                },
                                duration_ms=duration,
                            )

                        # OTP fallback：尽量不依赖邮件链接格式（仍不记录验证码到 artifacts）
                        if otp:
                            verify_url = f"{self.supabase_url}/auth/v1/verify"
                            verify_payload = {"type": "signup", "email": mailbox.email, "token": otp}
                            verify_headers = {
                                "apikey": self.supabase_service_key or self.supabase_anon_key,
                                "Authorization": f"Bearer {self.supabase_service_key or self.supabase_anon_key}",
                                "Content-Type": "application/json",
                            }
                            r = await client.post(
                                verify_url, json=verify_payload, headers=verify_headers, timeout=self.timeout
                            )
                            duration = self._now_ms() - start
                            return StepRecord(
                                name="supabase_confirm_email",
                                success=r.status_code in (200, 201, 204),
                                request={"url": verify_url, "mailbox_id": mailbox.mailbox_id},
                                response={"status_code": r.status_code},
                                notes={
                                    "method": "otp",
                                    "otp_len": len(otp),
                                    "otp_output_path": otp_output_path,
                                    "message_id": mid,
                                    "subject": subject,
                                    "checked_messages": checked,
                                },
                                duration_ms=duration,
                            )
                except Exception as exc:
                    last_error = str(exc)

                await asyncio.sleep(poll_interval_seconds)

        duration = self._now_ms() - start
        return StepRecord(
            name="supabase_confirm_email",
            success=False,
            request={"mailbox_id": mailbox.mailbox_id},
            response={"status_code": None},
            notes={
                "checked_messages": checked,
                "last_error": last_error,
                "last_message_id": last_message_id,
                "last_subject": last_subject,
            },
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
        saw_done = False
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
                            saw_done = True
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
            success=len(events) > 0 and (saw_done or any(e.get("event") == "data" for e in events)),
            request={"url": url},
            response={"status_code": status_code, "events": events},
            duration_ms=duration,
        )

    async def run(
        self,
        *,
        email_mode: str,
        mail_api_max_wait_seconds: float,
        mail_api_poll_interval_seconds: float,
        mail_api_domain: Optional[str],
        mail_api_expiry_ms: int,
        otp_output_path: Optional[str],
    ) -> int:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

        mailbox: Optional[Mailbox] = None
        local_domain = os.getenv("E2E_LOCAL_EMAIL_DOMAIN", "example.com").strip() or "example.com"
        email = f"anon-e2e-{int(time.time())}@{local_domain}"
        if email_mode == "mailapi":
            if not self.mail_api:
                print("ERROR: email_mode=mailapi 但未配置 MAIL_API_KEY")
                return await self._finalize(1)
            async with httpx.AsyncClient(timeout=self.timeout) as mail_client:
                domain = mail_api_domain
                if not domain:
                    try:
                        cfg = await self.mail_api.get_config(mail_client)
                    except Exception:
                        cfg = {}
                    candidates: set[str] = set()
                    self._collect_domain_candidates(cfg, candidates)
                    if candidates:
                        domain = sorted(candidates)[0]
                if not domain:
                    domain = "moemail.app"
                    print("[WARN] 未能从 Mail API /api/config 获取 domain，回退使用 moemail.app；建议显式设置 MAIL_DOMAIN。")

                name = f"anon_e2e_{int(time.time())}"
                try:
                    mailbox = await self.mail_api.generate_email(
                        mail_client,
                        name=name,
                        expiry_ms=mail_api_expiry_ms,
                        domain=domain,
                    )
                except Exception as exc:
                    self.report.add_step(
                        StepRecord(
                            name="mail_api_generate_email",
                            success=False,
                            request={"domain": domain, "expiry_ms": mail_api_expiry_ms},
                            response={"error": str(exc)},
                        )
                    )
                    print(f"ERROR: Mail API 生成邮箱失败: {exc}")
                    return await self._finalize(1)

            self.report.add_step(
                StepRecord(
                    name="mail_api_generate_email",
                    success=True,
                    request={"domain": domain, "expiry_ms": mail_api_expiry_ms},
                    response={"mailbox_id": mailbox.mailbox_id, "email": mailbox.email},
                )
            )
            email = mailbox.email

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
            login_step, token = await self._login_user(client, email, password)
            self.report.add_step(login_step)
            print(f"[STEP] Login status: {login_step.response['status_code']}")
            if not login_step.success and mailbox and self._is_email_not_confirmed(login_step.response.get("body")):
                confirm_step = await self._confirm_email_via_mail_api(
                    client,
                    mailbox=mailbox,
                    max_wait_seconds=mail_api_max_wait_seconds,
                    poll_interval_seconds=mail_api_poll_interval_seconds,
                    otp_output_path=otp_output_path,
                )
                self.report.add_step(confirm_step)
                if not confirm_step.success:
                    return await self._finalize(1)

                # 再试一次登录
                login_step_retry, token_retry = await self._login_user(client, email, password)
                login_step_retry.name = "supabase_login_retry"
                self.report.add_step(login_step_retry)
                print(f"[STEP] Login(retry) status: {login_step_retry.response['status_code']}")
                if not login_step_retry.success:
                    return await self._finalize(1)
                token = token_retry
            elif not login_step.success:
                return await self._finalize(1)
            else:
                token = token

            if not isinstance(token, str) or not token:
                return await self._finalize(1)

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

    # 优先使用 API_BASE_URL，其次向后兼容 API_BASE（不重复追加 /api/v1）
    raw_api_base = os.getenv("API_BASE_URL") or os.getenv("API_BASE")
    if raw_api_base:
        base = raw_api_base.rstrip("/")
        default_api_base = base if base.endswith("/api/v1") else f"{base}/api/v1"
    else:
        default_api_base = "http://localhost:9999/api/v1"

    parser.add_argument(
        "--api-base-url",
        default=default_api_base,
        help="后端 API 基础地址，优先来自 API_BASE_URL，其次 API_BASE，默认为 http://localhost:9999/api/v1",
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
    parser.add_argument(
        "--email-mode",
        choices=["auto", "local", "mailapi"],
        default=os.getenv("E2E_EMAIL_MODE", "auto"),
        help="邮箱来源：auto=有 MAIL_API_KEY 则 mailapi，否则 local；local=使用 test.local；mailapi=使用 Mail API",
    )
    parser.add_argument(
        "--mail-api-max-wait-seconds",
        type=float,
        default=float(os.getenv("MAIL_API_MAX_WAIT_SECONDS", "60")),
        help="等待确认邮件的最长时间（秒），默认 60",
    )
    parser.add_argument(
        "--mail-api-poll-interval-seconds",
        type=float,
        default=float(os.getenv("MAIL_API_POLL_INTERVAL_SECONDS", "2")),
        help="轮询 Mail API 的间隔（秒），默认 2",
    )
    parser.add_argument(
        "--mail-domain",
        default=os.getenv("MAIL_DOMAIN"),
        help="Mail API 域名（默认读 MAIL_DOMAIN；未设置时尝试从 /api/config 获取）",
    )
    parser.add_argument(
        "--mail-expiry-ms",
        type=int,
        default=int(os.getenv("MAIL_EXPIRY_MS", "3600000")),
        help="Mail API 邮箱有效期（毫秒），默认 3600000（1小时）",
    )
    parser.add_argument(
        "--otp-output-path",
        default=os.getenv("MAIL_OTP_OUTPUT_PATH"),
        help="可选：把 6 位验证码写到指定文件（例如 report/<run>/otp.txt），默认不写；注意用完请删除该文件",
    )
    parser.add_argument(
        "--print-mail-config",
        action="store_true",
        default=False,
        help="打印 Mail API /api/config（用于排查可用 domain）并退出",
    )
    parser.add_argument(
        "--debug-mailbox-id",
        default=None,
        help="调试 Mail API 邮箱内容（不输出确认链接/OTP原文），传入 mailbox_id 后打印摘要并退出",
    )
    return parser.parse_args()


async def async_main() -> int:
    load_env()
    args = parse_args()

    supabase_url = args.supabase_url or os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    anon_key = os.getenv("SUPABASE_ANON_KEY") or ""
    mail_api_key = os.getenv("MAIL_API_KEY") or os.getenv("api") or ""
    mail_api_base_url = os.getenv("MAIL_API_BASE_URL") or "https://taxbattle.xyz"

    async def _mail_debug(mailbox_id: str) -> int:
        if not mail_api_key:
            print("ERROR: 缺少 MAIL_API_KEY（或遗留别名 api），无法请求 Mail API")
            return 1
        api = MailApiClient(base_url=mail_api_base_url, api_key=mail_api_key)
        async with httpx.AsyncClient(timeout=float(os.getenv("E2E_HTTP_TIMEOUT", "30"))) as c:
            inbox = await api.list_messages(c, mailbox_id=mailbox_id)
            raw_messages: Any = inbox
            if isinstance(inbox, dict):
                for k in ("messages", "data", "items", "list"):
                    if isinstance(inbox.get(k), list):
                        raw_messages = inbox.get(k)
                        break
            messages = raw_messages if isinstance(raw_messages, list) else []
            msg0 = messages[0] if messages else None
            message_id = None
            if isinstance(msg0, dict):
                for k in ("messageId", "message_id", "id"):
                    v = msg0.get(k)
                    if isinstance(v, str) and v.strip():
                        message_id = v.strip()
                        break
            detail = await api.get_message(c, mailbox_id=mailbox_id, message_id=message_id) if message_id else {}

        # 只做摘要：不输出 tokenized link / OTP 原文
        strings: list[str] = []
        if isinstance(detail, dict):
            AnonymousE2E._collect_strings(detail, strings)  # type: ignore[attr-defined]
        blob = "\n".join(strings)
        urls = re.findall(r"https?://[^\s\"'<>]+", blob)
        verify_base = None
        for u in urls:
            if "/auth/v1/verify" in u:
                verify_base = u.split("?", 1)[0]
                break
        otp_match = re.search(r"\b(\d{6})\b", blob)

        summary = {
            "mailbox_id": mailbox_id,
            "messages_count": len(messages),
            "latest_message_id": message_id,
            "subject": (detail.get("subject") if isinstance(detail, dict) else None),
            "has_verify_link": bool(verify_base),
            "verify_url_base": verify_base,
            "has_otp": bool(otp_match),
            "otp_len": (len(otp_match.group(1)) if otp_match else None),
            "inbox_error": (inbox.get("error") if isinstance(inbox, dict) else None),
            "detail_error": (detail.get("error") if isinstance(detail, dict) else None),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.print_mail_config:
        if not mail_api_key:
            print("ERROR: 缺少 MAIL_API_KEY（或遗留别名 api），无法请求 /api/config")
            return 1
        client = MailApiClient(base_url=mail_api_base_url, api_key=mail_api_key)
        async with httpx.AsyncClient(timeout=float(os.getenv("E2E_HTTP_TIMEOUT", "30"))) as c:
            cfg = await client.get_config(c)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0

    if args.debug_mailbox_id:
        return await _mail_debug(args.debug_mailbox_id)

    missing = [
        name
        for name, value in [
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY", service_key or anon_key),
        ]
        if not value
    ]

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
    email_mode = args.email_mode
    if email_mode == "auto":
        email_mode = "mailapi" if mail_api_key else "local"

    if mail_api_key:
        if os.getenv("MAIL_API_KEY") is None and os.getenv("api"):
            print("[WARN] 检测到使用遗留环境变量 `api` 作为 Mail API Key；建议改为 `MAIL_API_KEY`。")
        runner.mail_api = MailApiClient(base_url=mail_api_base_url, api_key=mail_api_key)

    return await runner.run(
        email_mode=email_mode,
        mail_api_max_wait_seconds=args.mail_api_max_wait_seconds,
        mail_api_poll_interval_seconds=args.mail_api_poll_interval_seconds,
        mail_api_domain=args.mail_domain,
        mail_api_expiry_ms=args.mail_expiry_ms,
        otp_output_path=args.otp_output_path,
    )


def main() -> None:
    exit_code = asyncio.run(async_main())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
