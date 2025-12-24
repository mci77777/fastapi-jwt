#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass(frozen=True)
class Mailbox:
    mailbox_id: str
    email: str
    raw: Dict[str, Any]


class MailApiClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key}

    @staticmethod
    async def _error_text(resp: httpx.Response, limit: int = 500) -> str:
        try:
            text = resp.text
        except Exception:
            try:
                text = (await resp.aread()).decode("utf-8", "ignore")
            except Exception:
                text = "<unreadable>"
        text = text.strip()
        if len(text) > limit:
            return text[:limit] + "…"
        return text

    async def get_config(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        url = f"{self.base_url}/api/config"
        resp = await client.get(url, headers=self._headers())
        if not resp.is_success:
            return {"error": f"HTTP {resp.status_code}", "body": await self._error_text(resp)}
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"raw": data}
        except Exception:
            return {"raw": await self._error_text(resp)}

    async def generate_email(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        expiry_ms: int,
        domain: str,
    ) -> Mailbox:
        url = f"{self.base_url}/api/emails/generate"
        payload = {"name": name, "expiryTime": expiry_ms, "domain": domain}
        resp = await client.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload)
        if not resp.is_success:
            body = await self._error_text(resp)
            raise ValueError(f"Mail API generate_email failed: HTTP {resp.status_code}; body={body}")
        try:
            data = resp.json()
        except Exception:
            raise ValueError(f"Mail API /api/emails/generate 返回非 JSON：{await self._error_text(resp)}")
        if not isinstance(data, dict):
            raise ValueError("Mail API /api/emails/generate 返回值不是 JSON 对象")

        mailbox_id = (
            data.get("emailId")
            or data.get("email_id")
            or data.get("id")
            or (data.get("data") or {}).get("id")  # type: ignore[union-attr]
        )
        email = data.get("email") or data.get("address") or data.get("emailAddress") or data.get("mailbox")

        if not isinstance(mailbox_id, str) or not mailbox_id.strip():
            raise ValueError("Mail API 未返回有效的 emailId/id")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("Mail API 未返回有效的 email/address")

        return Mailbox(mailbox_id=mailbox_id, email=email, raw=data)

    async def list_messages(
        self,
        client: httpx.AsyncClient,
        *,
        mailbox_id: str,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/emails/{mailbox_id}"
        params: Dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        resp = await client.get(url, headers=self._headers(), params=params)
        if not resp.is_success:
            return {"error": f"HTTP {resp.status_code}", "body": await self._error_text(resp)}
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"messages": data}
        except Exception:
            return {"raw": await self._error_text(resp)}

    async def get_message(
        self,
        client: httpx.AsyncClient,
        *,
        mailbox_id: str,
        message_id: str,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/emails/{mailbox_id}/{message_id}"
        resp = await client.get(url, headers=self._headers())
        if not resp.is_success:
            return {"error": f"HTTP {resp.status_code}", "body": await self._error_text(resp)}
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"raw": data}
        except Exception:
            return {"raw": await self._error_text(resp)}
