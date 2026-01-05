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


def iter_auth_headers(api_key: str, url: str) -> list[dict[str, str]]:
    """根据目标 URL 返回“可能的鉴权头”候选列表（按优先级）。"""

    key = str(api_key or "").strip()
    if not key:
        return []

    # 默认：OpenAI 语义
    headers: list[dict[str, str]] = [{"Authorization": f"Bearer {key}"}]

    # 本地/内网代理：兼容 X-API-Key 或原始 Authorization
    if should_send_x_api_key(url):
        headers.append({"X-API-Key": key})
        headers.append({"Authorization": key})

    # 去重（保持顺序）
    seen: set[tuple[tuple[str, str], ...]] = set()
    unique: list[dict[str, str]] = []
    for item in headers:
        fingerprint = tuple(sorted((k.lower(), v) for k, v in item.items()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
    return unique


def is_retryable_auth_error(status_code: int, payload: object | None) -> bool:
    """仅对“显式 API key 鉴权失败”做重试（避免掩盖真实 401）。"""

    if status_code != 401:
        return False

    if not isinstance(payload, dict):
        return False

    for field in ("error", "message", "detail"):
        value = payload.get(field)
        if not isinstance(value, str):
            continue
        text = value.lower()
        if "api key" in text or "apikey" in text:
            return True
    return False
