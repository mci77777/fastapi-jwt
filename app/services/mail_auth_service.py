
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
import httpx
from app.settings.config import get_settings

logger = logging.getLogger(__name__)

class MailAuthService:
    """Mail API 认证服务，用于 E2E 测试和调试。"""

    def __init__(self, api_base: str = "https://taxbattle.xyz", api_key: Optional[str] = None):
        settings = get_settings()
        resolved_base = api_base
        base_from_settings = getattr(settings, "mail_api_base_url", None)
        if base_from_settings:
            resolved_base = str(base_from_settings)

        self.api_base = str(resolved_base).rstrip("/")
        self.api_key = api_key
        if not self.api_key:
            # 尝试从 settings 获取，或者抛出警告
            # 假设 settings 中会有 mail_api_key，如果没有暂时为空
            self.api_key = getattr(settings, "mail_api_key", None)

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("MAIL_API_KEY not configured")
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _extract_domains(config: Dict[str, Any]) -> list[str]:
        domains: list[str] = []

        raw_list = config.get("domains")
        if isinstance(raw_list, list):
            domains.extend([str(x).strip() for x in raw_list if str(x).strip()])

        raw_csv = (
            config.get("emailDomains")
            or config.get("email_domains")
            or config.get("availableDomains")
            or config.get("available_domains")
        )
        if isinstance(raw_csv, str) and raw_csv.strip():
            domains.extend([x.strip() for x in raw_csv.split(",") if x.strip()])
        elif isinstance(raw_csv, list):
            domains.extend([str(x).strip() for x in raw_csv if str(x).strip()])

        # 去重并保持顺序
        seen: set[str] = set()
        result: list[str] = []
        for d in domains:
            if d in seen:
                continue
            seen.add(d)
            result.append(d)
        return result

    async def get_config(self) -> Dict[str, Any]:
        """获取 Mail API 配置（可用域名等）。"""
        url = f"{self.api_base}/api/config"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()

    async def generate_email(
        self,
        domain: Optional[str] = None,
        name: str = "test",
        *,
        expiry_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """生成临时邮箱。"""
        if not domain:
            config = await self.get_config()
            domains = self._extract_domains(config)
            if not domains:
                raise ValueError("No available domains from Mail API")
            domain = domains[0]

        settings = get_settings()
        resolved_expiry_ms = (
            expiry_ms
            if isinstance(expiry_ms, int) and expiry_ms >= 0
            else int(getattr(settings, "mail_expiry_ms", 3600000) or 3600000)
        )
            
        url = f"{self.api_base}/api/emails/generate"
        payload = {
            "name": name,
            "expiryTime": resolved_expiry_ms,  # ms
            "domain": domain,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                # 兼容 taxbattle.xyz：返回 {id, email}，而非 {address}
                if not data.get("address"):
                    email = data.get("email")
                    if isinstance(email, str) and email.strip():
                        data["address"] = email.strip()
            return data

    async def get_emails(self, email_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
        """获取邮箱邮件列表。"""
        url = f"{self.api_base}/api/emails/{email_id}"
        params = {}
        if cursor:
            params["cursor"] = cursor
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._get_headers(), params=params)
            resp.raise_for_status()
            return resp.json()
            
    async def get_message(self, email_id: str, message_id: str) -> Dict[str, Any]:
        """获取单封邮件内容。"""
        url = f"{self.api_base}/api/emails/{email_id}/{message_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()

    async def wait_for_verification_code(self, email_id: str, timeout_seconds: int = 60) -> Optional[str]:
        """轮询等待验证码/魔法链接。"""
        start_time = time.time()
        cursor = None
        
        while time.time() - start_time < timeout_seconds:
            try:
                data = await self.get_emails(email_id, cursor)
                # data = { "items": [...], "nextCursor": ... }
                items = data.get("items", [])
                
                for item in items:
                    # 简单匹配逻辑：查找包含 'code' 或 'verify' 的邮件
                    # 实际需要下载邮件内容 self.get_message(email_id, item['id'])
                    msg_detail = await self.get_message(email_id, item['id'])
                    subject = msg_detail.get("subject", "")
                    body = msg_detail.get("text", "") or msg_detail.get("html", "")
                    
                    # 假设验证码是 6 位数字
                    import re
                    match = re.search(r'\b\d{6}\b', body) # 简单查找6位数字
                    if match:
                        return match.group(0)
                        
                    # 或者如果是 Magic Link，提取链接
                    # 这里简化为返回验证码，或者返回整个内容供调用者解析
                    
                # 更新 cursor
                if data.get("nextCursor"):
                    cursor = data["nextCursor"]
                    
            except Exception as e:
                logger.warning(f"Error checking emails: {e}")
                
            await asyncio.sleep(2)
            
        return None
