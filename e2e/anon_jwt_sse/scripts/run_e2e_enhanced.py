#!/usr/bin/env python3
"""
匿名用户端到端流程：
1. 调用 Supabase 邮箱注册 API 创建测试账号
2. 使用注册信息登录换取 JWT
3. 携带 JWT 调用 AI 消息接口发送 “hello”
4. 订阅 SSE 事件直到收到 completed/error
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
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

try:
    from mail_api_client import MailApiClient, Mailbox  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    from .mail_api_client import MailApiClient, Mailbox  # type: ignore[import-not-found]

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DEFAULT_OUTPUT = ARTIFACTS_DIR / "anon_e2e_trace.json"
DEFAULT_OUTPUT_TXT = ARTIFACTS_DIR / "anon_e2e_trace.txt"

# 默认附加 prompt（E2E/Web 默认启用）：要求模型原样输出包含尖括号标签的文本。
# 注意：此 prompt 仅用于 passthrough（skip_prompt=true），server 模式不注入（由后端 prompt SSOT 决定）。
DEFAULT_EXTRA_SYSTEM_PROMPT = (
    "请严格按原样输出带尖括号标签的 ThinkingML："
    "<thinking>...</thinking> 紧接 <final>...</final>。"
    "不要转义尖括号，不要额外解释协议。"
)


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
    request_id: str = ""
    user_email: str = ""
    steps: List[StepRecord] = field(default_factory=list)

    def add_step(self, step: StepRecord) -> None:
        self.steps.append(step)

    def to_json(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
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
        self.request_id = str(uuid.uuid4())
        self.report = TraceReport(
            started_at=time.time(),
            supabase_project_id=os.getenv("SUPABASE_PROJECT_ID"),
            supabase_url=self.supabase_url,
            api_base_url=self.api_base_url,
            request_id=self.request_id,
        )
        # 运行参数（用于 TXT 报告）
        self._output_txt_path: Optional[Path] = None
        self._result_mode: str = "text"
        self._prompt_mode: str = "passthrough"
        self._extra_system_prompt: str = DEFAULT_EXTRA_SYSTEM_PROMPT
        self._models: list[str] = []
        self._concurrency: int = 1
        self._message_text: str = "hello"
        self._model_runs: list[dict[str, Any]] = []

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
    def _mask_email(email: str) -> str:
        if not email or "@" not in email:
            return "<redacted>"
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            return f"{local[:1]}***@{domain}"
        return f"{local[:2]}***@{domain}"

    @staticmethod
    def _safe_sse_event(event: str, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict):
            if event == "content_delta":
                delta = str(data.get("delta") or "")
                return {
                    "event": event,
                    "data": {
                        "message_id": data.get("message_id"),
                        "delta_len": len(delta),
                        "delta_preview": delta[:20],
                        "request_id": data.get("request_id"),
                    },
                }
            if event == "completed":
                reply = str(data.get("reply") or "")
                reply_len = data.get("reply_len")
                if not isinstance(reply_len, int):
                    reply_len = len(reply)
                return {
                    "event": event,
                    "data": {
                        "message_id": data.get("message_id"),
                        "reply_len": reply_len,
                        "reply_preview": reply[:40] if reply else None,
                        "request_id": data.get("request_id"),
                    },
                }
            if event == "error":
                return {
                    "event": event,
                    "data": {
                        "message_id": data.get("message_id"),
                        "code": data.get("code"),
                        "error": data.get("error"),
                        "request_id": data.get("request_id"),
                    },
                }
        return {"event": event, "data": data}

    @staticmethod
    def _parse_models(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            raw_list = [str(v) for v in value]
        else:
            raw_list = re.split(r"[,\s]+", str(value or "").strip())
        items: list[str] = []
        for v in raw_list:
            text = str(v or "").strip()
            if text:
                items.append(text)
        # 去重但保序
        seen: set[str] = set()
        out: list[str] = []
        for m in items:
            if m in seen:
                continue
            seen.add(m)
            out.append(m)
        return out

    async def _list_app_models(self, client: httpx.AsyncClient, token: str) -> list[str]:
        """拉取 App 可发送的 model keys（SSOT：/llm/app/models）。失败时返回空列表。"""

        url = f"{self.api_base_url}/llm/app/models"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-Id": self.request_id,
        }
        try:
            resp = await client.get(url, headers=headers, params={"only_active": "true"}, timeout=self.timeout)
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        body = _safe_json(resp)
        if not isinstance(body, dict):
            return []

        recommended = str(body.get("recommended_model") or body.get("recommendedModel") or "").strip()
        items = body.get("data")
        if not isinstance(items, list):
            items = []

        out: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                out.append(name)

        # 优先把 recommended 放到列表首位（若存在）
        if recommended:
            out = [m for m in out if m != recommended]
            out.insert(0, recommended)
        return out

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

    @staticmethod
    def _extract_verify_params_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 Supabase /auth/v1/verify 链接中提取 (type, token)。

        兼容 token / token_hash 两种 query key（不同版本或模板可能不同）。
        """
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            verify_type = qs.get("type", [None])[0]
            token = qs.get("token", [None])[0] or qs.get("token_hash", [None])[0]
            return (verify_type if isinstance(verify_type, str) else None), (token if isinstance(token, str) else None)
        except Exception:
            return None, None

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

    async def _login_via_signup_otp_mail_api(
        self,
        client: httpx.AsyncClient,
        *,
        mailbox: Mailbox,
        max_wait_seconds: float,
        poll_interval_seconds: float,
        otp_output_path: Optional[str],
    ) -> tuple[StepRecord, Optional[str]]:
        """
        通过“注册确认邮件”里的 OTP / verify 链接，直接换取 access_token（避免 password grant）。

        适用场景：用户希望“注册 + 验证码(OTP)登录”闭环。
        """
        if not self.mail_api:
            return (
                StepRecord(name="supabase_login_otp", success=False, notes={"error": "mail_api_not_configured"}),
                None,
            )

        start = self._now_ms()
        deadline = time.monotonic() + max_wait_seconds
        checked = 0
        last_error: Optional[str] = None
        last_message_id: Optional[str] = None
        last_subject: Optional[str] = None
        seen: set[str] = set()

        verify_url = f"{self.supabase_url}/auth/v1/verify"
        verify_headers = {
            "apikey": self.supabase_anon_key or self.supabase_service_key,
            "Authorization": f"Bearer {self.supabase_anon_key or self.supabase_service_key}",
            "Content-Type": "application/json",
        }

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

                        otp = self._extract_otp(text)
                        urls = re.findall(r"https?://[^\s\"'<>]+", text)
                        verify_link = None
                        for u in urls:
                            if "/auth/v1/verify" in u:
                                verify_link = u
                                break

                        # 可选：导出 OTP 供人工确认（不写入 trace/artifacts）
                        if otp_output_path and otp:
                            try:
                                Path(otp_output_path).write_text(f"email={mailbox.email}\notp={otp}\n", encoding="utf-8")
                            except Exception:
                                pass

                        verify_type = "signup"
                        token_for_verify = otp
                        if not token_for_verify and verify_link:
                            link_type, link_token = self._extract_verify_params_from_url(verify_link)
                            if isinstance(link_type, str) and link_type.strip():
                                verify_type = link_type.strip()
                            token_for_verify = link_token

                        if not token_for_verify:
                            continue

                        payload = {"type": verify_type, "email": mailbox.email, "token": token_for_verify}
                        r = await client.post(verify_url, json=payload, headers=verify_headers, timeout=self.timeout)
                        body = _safe_json(r)
                        token = body.get("access_token") if isinstance(body, dict) else None

                        duration = self._now_ms() - start
                        if otp_output_path:
                            try:
                                meta_path = Path(otp_output_path).with_name("mail_meta.json")
                                meta = {
                                    "email": mailbox.email,
                                    "mailbox_id": mailbox.mailbox_id,
                                    "checked_messages": checked,
                                    "message_id": mid,
                                    "subject": subject,
                                    "verify_url_base": (verify_link.split("?", 1)[0] if verify_link else None),
                                    "verify_type": verify_type,
                                    "has_otp": bool(otp),
                                    "otp_len": (len(otp) if otp else None),
                                    "otp_output_path": otp_output_path,
                                    "otp_verify_status": r.status_code,
                                    "has_access_token": isinstance(token, str),
                                    "access_token_len": (len(token) if isinstance(token, str) else None),
                                }
                                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                            except Exception:
                                pass

                        step = StepRecord(
                            name="supabase_login_otp",
                            success=r.status_code == 200 and isinstance(token, str) and bool(token),
                            request={"url": verify_url, "mailbox_id": mailbox.mailbox_id, "type": verify_type},
                            response={"status_code": r.status_code, "body": self._redact_tokens(body)},
                            notes={
                                "checked_messages": checked,
                                "message_id": mid,
                                "subject": subject,
                                "otp_len": (len(otp) if otp else None),
                                "access_token_len": (len(token) if isinstance(token, str) else None),
                                "otp_output_path": otp_output_path,
                            },
                            duration_ms=duration,
                        )
                        return step, (token if isinstance(token, str) else None)
                except Exception as exc:
                    last_error = str(exc)

                await asyncio.sleep(poll_interval_seconds)

        duration = self._now_ms() - start
        return (
            StepRecord(
                name="supabase_login_otp",
                success=False,
                request={"mailbox_id": mailbox.mailbox_id},
                response={"status_code": None},
                notes={
                    "checked_messages": checked,
                    "last_error": last_error,
                    "last_message_id": last_message_id,
                    "last_subject": last_subject,
                    "otp_output_path": otp_output_path,
                },
                duration_ms=duration,
            ),
            None,
        )

    async def _login_via_signup_otp_admin_generate_link(
        self,
        client: httpx.AsyncClient,
        *,
        email: str,
        password: str,
    ) -> tuple[StepRecord, Optional[str]]:
        """
        通过 service_role 的 admin generate_link 生成 signup verify link/otp，
        再调用 /auth/v1/verify 换取 access_token。

        用于在缺少 Mail API Key 的情况下，仍能验证“验证码(OTP)登录”闭环。
        """
        if not self.supabase_service_key:
            return (
                StepRecord(
                    name="supabase_login_otp",
                    success=False,
                    notes={"error": "missing_SUPABASE_SERVICE_ROLE_KEY_for_admin_generate_link"},
                ),
                None,
            )

        admin_url = f"{self.supabase_url}/auth/v1/admin/generate_link"
        admin_headers = {
            "apikey": self.supabase_service_key,
            "Authorization": f"Bearer {self.supabase_service_key}",
            "Content-Type": "application/json",
        }
        admin_payload: Dict[str, Any] = {"type": "signup", "email": email, "password": password}

        start = self._now_ms()
        admin_resp = await client.post(admin_url, json=admin_payload, headers=admin_headers, timeout=self.timeout)
        admin_body = _safe_json(admin_resp)

        # 尽量从响应中提取 verify link/otp，但不把敏感字段写入 trace
        action_link = None
        email_otp = None
        if isinstance(admin_body, dict):
            action_link = admin_body.get("action_link")
            email_otp = admin_body.get("email_otp") or admin_body.get("otp")

        verify_type = "signup"
        token_for_verify: Optional[str] = None
        if isinstance(email_otp, str) and email_otp.strip():
            token_for_verify = email_otp.strip()
        elif isinstance(action_link, str) and action_link.strip():
            link_type, link_token = self._extract_verify_params_from_url(action_link)
            if isinstance(link_type, str) and link_type.strip():
                verify_type = link_type.strip()
            token_for_verify = link_token

        verify_url = f"{self.supabase_url}/auth/v1/verify"
        verify_headers = {
            "apikey": self.supabase_anon_key or self.supabase_service_key,
            "Authorization": f"Bearer {self.supabase_anon_key or self.supabase_service_key}",
            "Content-Type": "application/json",
        }

        token: Optional[str] = None
        verify_status: Optional[int] = None
        verify_body: Any = None
        if token_for_verify:
            verify_payload = {"type": verify_type, "email": email, "token": token_for_verify}
            r = await client.post(verify_url, json=verify_payload, headers=verify_headers, timeout=self.timeout)
            verify_status = r.status_code
            verify_body = _safe_json(r)
            token = verify_body.get("access_token") if isinstance(verify_body, dict) else None

        duration = self._now_ms() - start
        step = StepRecord(
            name="supabase_login_otp",
            success=(admin_resp.status_code == 200)
            and (verify_status == 200)
            and isinstance(token, str)
            and bool(token),
            request={
                "admin_url": admin_url,
                "admin_payload": self._redact_password(admin_payload),
                "verify_url": verify_url,
                "verify_type": verify_type,
            },
            response={
                "admin_status_code": admin_resp.status_code,
                "admin_body": {
                    "has_action_link": isinstance(action_link, str) and bool(action_link),
                    "has_email_otp": isinstance(email_otp, str) and bool(email_otp),
                },
                "verify_status_code": verify_status,
                "verify_body": self._redact_tokens(verify_body) if verify_body is not None else None,
            },
            notes={
                "access_token_len": (len(token) if isinstance(token, str) else None),
                "token_source": ("email_otp" if isinstance(email_otp, str) and bool(email_otp) else "action_link"),
            },
            duration_ms=duration,
        )
        return step, (token if isinstance(token, str) else None)

    async def _send_message(
        self,
        client: httpx.AsyncClient,
        token: str,
        *,
        request_id: str,
        model_key: Optional[str],
        prompt_mode: str,
        extra_system_prompt: str,
        message_text: str,
    ) -> StepRecord:
        url = f"{self.api_base_url}/messages"
        resolved_model_key = str(model_key or "").strip() or None
        resolved_prompt_mode = "passthrough" if str(prompt_mode or "").strip() == "passthrough" else "server"
        text = str(message_text or "").strip() or "hello"

        metadata: Dict[str, Any] = {
            "source": "anon_e2e",
            "prompt_mode": resolved_prompt_mode,
        }
        if resolved_model_key:
            metadata["model"] = resolved_model_key

        payload: Dict[str, Any] = {
            "conversation_id": None,
            "metadata": metadata,
        }
        if resolved_model_key:
            payload["model"] = resolved_model_key

        if resolved_prompt_mode == "passthrough":
            payload["skip_prompt"] = True
            system_text = str(extra_system_prompt or "").strip() or DEFAULT_EXTRA_SYSTEM_PROMPT
            payload["messages"] = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": text},
            ]
        else:
            payload["skip_prompt"] = False
            payload["text"] = text

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
        }

        start = self._now_ms()
        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout)
        duration = self._now_ms() - start

        body = _safe_json(resp)
        message_id = body.get("message_id") if isinstance(body, dict) else None
        conversation_id = body.get("conversation_id") if isinstance(body, dict) else None

        return StepRecord(
            name=f"api_create_message(model={resolved_model_key or 'default'},prompt={resolved_prompt_mode})",
            success=resp.status_code in (200, 202) and isinstance(message_id, str) and isinstance(conversation_id, str),
            request={"url": url, "headers": {"X-Request-Id": request_id}, "payload": payload},
            response={"status_code": resp.status_code, "body": body},
            notes={
                "request_id": request_id,
                "model": resolved_model_key,
                "prompt_mode": resolved_prompt_mode,
                "message_id": message_id,
                "conversation_id": conversation_id,
            },
            duration_ms=duration,
        )

    async def _stream_events(
        self,
        client: httpx.AsyncClient,
        token: str,
        message_id: str,
        conversation_id: str,
        *,
        request_id: str,
    ) -> tuple[StepRecord, Optional[str], Optional[Dict[str, Any]]]:
        url = f"{self.api_base_url}/messages/{message_id}/events"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "X-Request-Id": request_id,
        }

        frames: List[Dict[str, Any]] = []
        final_event: Optional[Dict[str, Any]] = None
        final_reply_text: Optional[str] = None
        status_code = None
        start = self._now_ms()

        current_event: str = "message"
        data_lines: List[str] = []
        # 原始 SSE 摘要：只保留首条 content_delta 与终止事件（completed/error）的原文，便于 App↔后端契约对齐。
        raw_first_content_delta: Optional[str] = None
        raw_terminal_event: Optional[str] = None

        def flush() -> Optional[Dict[str, Any]]:
            nonlocal data_lines, current_event
            if not data_lines:
                return None
            raw = "\n".join(data_lines)
            data_lines = []
            parsed = _safe_parse_json(raw)
            return {"event": current_event or "message", "data": parsed}

        try:
            async with client.stream(
                "GET",
                url,
                headers=headers,
                params={"conversation_id": conversation_id},
                timeout=None,
            ) as resp:
                status_code = resp.status_code

                if resp.status_code != 200:
                    text = await resp.aread()
                    return (
                        StepRecord(
                            name="api_stream_events",
                            success=False,
                            request={
                                "url": url,
                                "headers": {"X-Request-Id": request_id},
                                "params": {"conversation_id": conversation_id},
                            },
                            response={"status_code": resp.status_code, "body": text.decode("utf-8", "ignore")},
                            duration_ms=self._now_ms() - start,
                        ),
                        None,
                        None,
                    )

                async for line in resp.aiter_lines():
                    if line is None:
                        continue
                    line = line.rstrip("\r")

                    if line == "":
                        # 捕获“原始 SSE 行”（event/data），仅用于对齐契约，不写入 token 等敏感信息。
                        if current_event in ("content_delta", "completed", "error") and data_lines:
                            raw_data = "\n".join(data_lines)
                            if current_event == "content_delta" and raw_first_content_delta is None:
                                raw_first_content_delta = f"event: {current_event}\ndata: {raw_data}\n"
                            if current_event in ("completed", "error") and raw_terminal_event is None:
                                raw_terminal_event = f"event: {current_event}\ndata: {raw_data}\n"

                        evt = flush()
                        if evt:
                            frames.append(self._safe_sse_event(str(evt.get("event")), evt.get("data")))
                            if evt.get("event") in ("completed", "error"):
                                final_event = evt
                                data = evt.get("data")
                                if isinstance(data, dict) and isinstance(data.get("reply"), str):
                                    final_reply_text = str(data.get("reply") or "")
                                break
                        current_event = "message"
                        continue

                    if line.startswith("event:"):
                        current_event = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:") :].strip())
        except Exception as exc:  # pragma: no cover
            return (
                StepRecord(
                    name="api_stream_events",
                    success=False,
                    request={"url": url},
                    response={"status_code": status_code, "body": str(exc)},
                    duration_ms=self._now_ms() - start,
                    notes={"error": str(exc)},
                ),
                None,
                None,
            )

        duration = self._now_ms() - start
        final_name = final_event.get("event") if isinstance(final_event, dict) else None
        ok = bool(final_event) and len(frames) > 0 and final_name == "completed"

        safe_final: Optional[Dict[str, Any]] = None
        if isinstance(final_event, dict) and final_name in ("completed", "error"):
            safe_final = self._safe_sse_event(final_name, final_event.get("data"))

        notes: Dict[str, Any] = {
            "frames": frames[:200],
        }
        if raw_first_content_delta or raw_terminal_event:
            notes["raw_sse_excerpt"] = {
                "first_content_delta": raw_first_content_delta,
                "terminal_event": raw_terminal_event,
            }

        # 对账：completed/error 的 request_id 必须与 create 的 X-Request-Id 一致
        if isinstance(final_event, dict) and final_name in ("completed", "error"):
            data = final_event.get("data")
            if isinstance(data, dict) and data.get("request_id") and data.get("request_id") != request_id:
                ok = False
                notes["request_id_mismatch"] = True

        # 强约束：出现 error 视为 E2E 失败（用于检测上游密钥/策略漂移）
        if final_name == "error":
            notes["final_error"] = True

        return (
            StepRecord(
                name="api_stream_events",
                success=ok,
                request={
                    "url": url,
                    "headers": {"X-Request-Id": request_id},
                    "params": {"conversation_id": conversation_id},
                },
                response={
                    "status_code": status_code,
                    "frames_count": len(frames),
                    "final_event": safe_final,
                },
                notes=notes,
                duration_ms=duration,
            ),
            final_reply_text,
            final_event,
        )

    async def run(
        self,
        *,
        auth_method: str,
        email_mode: str,
        mail_api_max_wait_seconds: float,
        mail_api_poll_interval_seconds: float,
        mail_api_domain: Optional[str],
        mail_api_expiry_ms: int,
        otp_output_path: Optional[str],
        prompt_mode: str,
        extra_system_prompt: str,
        models: list[str],
        concurrency: int,
        result_mode: str,
        output_txt_path: Optional[Path],
        message_text: str,
    ) -> int:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        self._output_txt_path = output_txt_path
        raw_result_mode = str(result_mode or "").strip()
        self._result_mode = "raw" if raw_result_mode == "raw" else ("both" if raw_result_mode == "both" else "text")
        self._prompt_mode = "passthrough" if str(prompt_mode or "").strip() == "passthrough" else "server"
        self._extra_system_prompt = str(extra_system_prompt or "").strip() or DEFAULT_EXTRA_SYSTEM_PROMPT
        self._models = list(models or [])
        self._concurrency = max(int(concurrency or 1), 1)
        self._message_text = str(message_text or "").strip() or "hello"

        mailbox: Optional[Mailbox] = None
        local_domain = os.getenv("E2E_LOCAL_EMAIL_DOMAIN", "example.com").strip() or "example.com"
        email = f"anon-e2e-{int(time.time())}@{local_domain}"
        if email_mode == "mailapi":
            if not self.mail_api:
                if auth_method == "otp":
                    print("[WARN] email_mode=mailapi 但未配置 MAIL_API_KEY：将回退为 local email，并使用 admin generate_link 走 OTP 登录验证。")
                    email_mode = "local"
                else:
                    print("ERROR: email_mode=mailapi 但未配置 MAIL_API_KEY")
                    return await self._finalize(1)
            if email_mode == "mailapi":
                async with httpx.AsyncClient(timeout=self.timeout) as mail_client:
                    domain = mail_api_domain
                    if not domain:
                        try:
                            cfg = await self.mail_api.get_config(mail_client)  # type: ignore[union-attr]
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
                        mailbox = await self.mail_api.generate_email(  # type: ignore[union-attr]
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
        self.report.user_email = self._mask_email(email)

        print(f"request_id={self.request_id} action=start_anon_e2e api_base={self.api_base_url}")
        print(f"request_id={self.request_id} temp_email={self._mask_email(email)}")
        self.report.add_step(
            StepRecord(
                name="e2e_config",
                success=True,
                notes={
                    "prompt_mode": self._prompt_mode,
                    "extra_system_prompt_len": len(self._extra_system_prompt or ""),
                    "models": self._models,
                    "concurrency": self._concurrency,
                    "result_mode": self._result_mode,
                    "message_text_len": len(self._message_text),
                },
            )
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 注册
            signup_step = await self._register_user(client, email, password)
            self.report.add_step(signup_step)
            print(f"request_id={self.request_id} step=supabase_signup status={signup_step.response['status_code']}")
            if not signup_step.success:
                return await self._finalize(1)

            token: Optional[str] = None

            if auth_method == "otp":
                if not mailbox:
                    login_step, token = await self._login_via_signup_otp_admin_generate_link(
                        client, email=email, password=password
                    )
                    self.report.add_step(login_step)
                    print(
                        f"request_id={self.request_id} step=supabase_login_otp_adminlink status={login_step.response.get('verify_status_code')}"
                    )
                    if not login_step.success:
                        return await self._finalize(1)
                else:
                    login_step, token = await self._login_via_signup_otp_mail_api(
                        client,
                        mailbox=mailbox,
                        max_wait_seconds=mail_api_max_wait_seconds,
                        poll_interval_seconds=mail_api_poll_interval_seconds,
                        otp_output_path=otp_output_path,
                    )
                    self.report.add_step(login_step)
                    print(f"request_id={self.request_id} step=supabase_login_otp status={login_step.response.get('status_code')}")
                    if not login_step.success:
                        return await self._finalize(1)
            else:
                # 登录换取 JWT（password grant）
                login_step, token = await self._login_user(client, email, password)
                self.report.add_step(login_step)
                print(f"request_id={self.request_id} step=supabase_login_password status={login_step.response['status_code']}")
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
                    print(
                        f"request_id={self.request_id} step=supabase_login_password_retry status={login_step_retry.response['status_code']}"
                    )
                    if not login_step_retry.success:
                        return await self._finalize(1)
                    token = token_retry
                elif not login_step.success:
                    return await self._finalize(1)

            if not isinstance(token, str) or not token:
                return await self._finalize(1)

            selected_models = [m for m in (self._models or []) if str(m or "").strip()]
            # 约定：仅当用户显式传入 --models auto / --models '*' 时，才自动拉取 /llm/app/models。
            # 未提供 --models 时默认走 default model（避免把未配置 key 的模型也跑进来导致 E2E 恒失败）。
            wants_auto = False
            if selected_models:
                lowered = [str(m).strip().lower() for m in selected_models]
                wants_auto = len(selected_models) == 1 and (lowered[0] == "auto" or selected_models[0].strip() == "*")

            if not selected_models:
                # 默认选择：优先取 /llm/app/models 的 recommended_model（或首个可用）
                # 说明：后端 /messages schema 可能要求显式传 model；因此默认不能省略。
                try:
                    candidates = await self._list_app_models(client, token)
                except Exception:
                    candidates = []
                if candidates:
                    selected_models = [candidates[0]]
                else:
                    self.report.add_step(
                        StepRecord(
                            name="e2e_select_default_model_failed",
                            success=False,
                            response={"error": "no_app_models"},
                            notes={"hint": "请显式传 --models <key1,key2> 或使用 --models auto / '*'"},
                        )
                    )
                    return await self._finalize(1)
            elif wants_auto:
                try:
                    selected_models = await self._list_app_models(client, token)
                except Exception:
                    selected_models = []
                if not selected_models:
                    self.report.add_step(
                        StepRecord(
                            name="e2e_list_app_models_failed",
                            success=False,
                            response={"error": "no_app_models"},
                            notes={"hint": "请显式传 --models <key1,key2>"},
                        )
                    )
                    return await self._finalize(1)
            else:
                # 若用户混入 auto/*，直接忽略该占位符（KISS：避免歧义）
                selected_models = [m for m in selected_models if str(m).strip().lower() not in {"auto", "*"}]
                if not selected_models:
                    self.report.add_step(
                        StepRecord(
                            name="e2e_models_empty_after_filter",
                            success=False,
                            response={"error": "invalid_models"},
                            notes={"hint": "请显式传 --models <key1,key2> 或使用 --models auto / '*'"},
                        )
                    )
                    return await self._finalize(1)

            async def run_one(idx: int, raw_model: str) -> dict[str, Any]:
                model_key = str(raw_model or "").strip() or None
                per_request_id = str(uuid.uuid4())
                create_step = await self._send_message(
                    client,
                    token,
                    request_id=per_request_id,
                    model_key=model_key,
                    prompt_mode=self._prompt_mode,
                    extra_system_prompt=self._extra_system_prompt,
                    message_text=self._message_text,
                )
                message_id = create_step.notes.get("message_id")
                conversation_id = create_step.notes.get("conversation_id")
                if not create_step.success or not isinstance(message_id, str) or not isinstance(conversation_id, str):
                    return {
                        "idx": idx,
                        "model": model_key,
                        "request_id": per_request_id,
                        "create_step": create_step,
                        "events_step": None,
                        "success": False,
                        "reply": None,
                        "final_event": None,
                    }

                events_step, reply_text, final_event = await self._stream_events(
                    client,
                    token,
                    message_id,
                    conversation_id,
                    request_id=per_request_id,
                )
                return {
                    "idx": idx,
                    "model": model_key,
                    "request_id": per_request_id,
                    "create_step": create_step,
                    "events_step": events_step,
                    "success": bool(events_step.success),
                    "reply": reply_text,
                    "final_event": final_event,
                }

            sem = asyncio.Semaphore(self._concurrency)

            async def bounded(idx: int, model_key: str) -> dict[str, Any]:
                async with sem:
                    return await run_one(idx, model_key)

            tasks = [bounded(i, m) for i, m in enumerate(selected_models)]
            raw_results = await asyncio.gather(*tasks, return_exceptions=False)
            results = sorted(raw_results, key=lambda item: int(item.get("idx", 0)))

            ok_all = True
            for item in results:
                create_step = item.get("create_step")
                events_step = item.get("events_step")
                if isinstance(create_step, StepRecord):
                    self.report.add_step(create_step)
                    print(
                        f"request_id={item.get('request_id')} step=create_message model={item.get('model') or 'default'} "
                        f"status={create_step.response.get('status_code')}"
                    )
                if isinstance(events_step, StepRecord):
                    self.report.add_step(events_step)
                    print(
                        f"request_id={item.get('request_id')} step=stream_events model={item.get('model') or 'default'} "
                        f"status={events_step.response.get('status_code')}"
                    )
                if not bool(item.get("success")):
                    ok_all = False

            self._model_runs = results
            if not ok_all:
                return await self._finalize(1)

        return await self._finalize(0)

    async def _finalize(self, exit_code: int) -> int:
        self.report.finished_at = time.time()
        with self.output_path.open("w", encoding="utf-8") as fp:
            json.dump(self.report.to_json(), fp, ensure_ascii=False, indent=2)
        print(f"[INFO] Full trace saved to: {self.output_path}")
        # 默认 TXT 报告：包含 completed.reply 原文（含尖括号标签），便于人工核对。
        txt_path = self._output_txt_path
        if txt_path is None:
            if self.output_path.suffix.lower() == ".json":
                txt_path = self.output_path.with_suffix(".txt")
            else:
                txt_path = DEFAULT_OUTPUT_TXT
        try:
            lines: list[str] = []
            lines.append(f"request_id={self.request_id}")
            lines.append(f"api_base_url={self.api_base_url}")
            lines.append(f"prompt_mode={self._prompt_mode}")
            lines.append(f"concurrency={self._concurrency}")
            raw_models = [m for m in (self._models or []) if str(m or "").strip()]
            lowered = [str(m).strip().lower() for m in raw_models]
            is_auto = len(raw_models) == 1 and (lowered[0] == "auto" or str(raw_models[0]).strip() == "*")
            models_label = ",".join([m for m in raw_models if str(m).strip().lower() not in {"auto", "*"}])
            if is_auto:
                models_label = "auto"
            elif not models_label:
                models_label = "recommended"
            lines.append(f"models={models_label}")
            lines.append("")

            for item in (self._model_runs or []):
                model_key = item.get("model") or "default"
                per_request_id = item.get("request_id") or ""
                success = bool(item.get("success"))
                lines.append(f"=== model={model_key} request_id={per_request_id} status={'PASS' if success else 'FAIL'} ===")
                reply = item.get("reply")
                final_event = item.get("final_event")
                events_step = item.get("events_step")
                raw_excerpt = None
                if isinstance(events_step, StepRecord):
                    raw_excerpt = (events_step.notes or {}).get("raw_sse_excerpt")

                if isinstance(reply, str) and reply.strip():
                    lines.append(reply)
                elif isinstance(final_event, dict):
                    data = final_event.get("data")
                    if isinstance(data, dict):
                        msg = data.get("message") or data.get("error") or data.get("code")
                        if msg:
                            lines.append(str(msg))
                        else:
                            lines.append("(no_reply)")
                    else:
                        lines.append("(no_reply)")
                else:
                    lines.append("(no_reply)")

                if raw_excerpt and isinstance(raw_excerpt, dict):
                    first_delta = raw_excerpt.get("first_content_delta")
                    terminal = raw_excerpt.get("terminal_event")
                    if isinstance(first_delta, str) or isinstance(terminal, str):
                        lines.append("")
                        lines.append("--- sse_raw_excerpt ---")
                        if isinstance(first_delta, str) and first_delta.strip():
                            lines.append(first_delta.rstrip())
                            lines.append("")
                        if isinstance(terminal, str) and terminal.strip():
                            lines.append(terminal.rstrip())

                if self._result_mode in {"raw", "both"}:
                    try:
                        lines.append("")
                        lines.append("--- raw ---")
                        lines.append(json.dumps(final_event, ensure_ascii=False, indent=2))
                    except Exception:
                        pass
                lines.append("")

            txt_path.parent.mkdir(parents=True, exist_ok=True)
            txt_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            print(f"[INFO] TXT report saved to: {txt_path}")
        except Exception:
            pass
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
        "--output-txt",
        default=None,
        help=f"可选：TXT 报告输出路径（默认与 --output 同名 .txt，或 {DEFAULT_OUTPUT_TXT}）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("E2E_HTTP_TIMEOUT", "30")),
        help="HTTP 请求超时时间（秒），默认为 30",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=["passthrough", "server"],
        default=os.getenv("E2E_PROMPT_MODE", "passthrough"),
        help="prompt 策略：passthrough=透传 messages(system+user) 且 skip_prompt=true；server=只发 text 且由后端注入默认 prompt",
    )
    parser.add_argument(
        "--extra-system-prompt",
        default=os.getenv("E2E_EXTRA_SYSTEM_PROMPT", DEFAULT_EXTRA_SYSTEM_PROMPT),
        help="passthrough 模式下追加的 system prompt（默认非空，用于强调尖括号标签原样输出；传空字符串可关闭）",
    )
    parser.add_argument(
        "--models",
        default=os.getenv("E2E_MODELS", ""),
        help=(
            "可选：逗号/空格分隔的 model keys（如 xai,deepseek）。"
            "未提供时会从 /llm/app/models 选取 recommended_model（或首个可用）作为默认；"
            "传入 auto 或 '*' 则从 /llm/app/models 自动选择全部可用模型。"
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("E2E_CONCURRENCY", "1")),
        help="并发数（默认 1；过高可能触发 SSE 并发守卫/限流）。",
    )
    parser.add_argument(
        "--result-mode",
        choices=["text", "raw", "both"],
        default=os.getenv("E2E_RESULT_MODE", "text"),
        help="TXT 报告内容：text=仅 reply；raw=仅 raw final_event；both=两者都写。",
    )
    parser.add_argument(
        "--message",
        default=os.getenv("E2E_MESSAGE", "hello"),
        help="用户消息内容（默认 hello）。",
    )
    parser.add_argument(
        "--auth-method",
        choices=["password", "otp"],
        default=os.getenv("E2E_AUTH_METHOD", "password"),
        help="登录方式：password=邮箱+密码换取 JWT；otp=使用注册确认邮件里的验证码(OTP)换取 JWT（需要 email_mode=mailapi）",
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

    models = AnonymousE2E._parse_models(args.models)
    output_txt = Path(args.output_txt) if args.output_txt else None

    return await runner.run(
        auth_method=args.auth_method,
        email_mode=email_mode,
        mail_api_max_wait_seconds=args.mail_api_max_wait_seconds,
        mail_api_poll_interval_seconds=args.mail_api_poll_interval_seconds,
        mail_api_domain=args.mail_domain,
        mail_api_expiry_ms=args.mail_expiry_ms,
        otp_output_path=args.otp_output_path,
        prompt_mode=args.prompt_mode,
        extra_system_prompt=str(args.extra_system_prompt or ""),
        models=models,
        concurrency=args.concurrency,
        result_mode=args.result_mode,
        output_txt_path=output_txt,
        message_text=str(args.message or ""),
    )


def main() -> None:
    exit_code = asyncio.run(async_main())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
