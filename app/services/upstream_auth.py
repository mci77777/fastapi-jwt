"""上游鉴权头（兼容 OpenAI 语义与本地代理）。"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}


def should_send_x_api_key(url: str) -> bool:
    """仅在“明显为本地/内网目标”时，额外发送 X-API-Key。

    目的：兼容一些本地代理/网关只识别 X-API-Key，而不是 Authorization: Bearer。
    """

    text = str(url or "").strip()
    if not text:
        return False

    try:
        host = (urlsplit(text).hostname or "").strip().lower()
    except Exception:
        return False

    if not host:
        return False
    if host in _LOCAL_HOSTS:
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)

