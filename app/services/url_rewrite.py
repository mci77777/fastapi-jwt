"""容器环境 URL 重写（SSOT）。"""

from __future__ import annotations

import os
from urllib.parse import SplitResult, urlsplit, urlunsplit


_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_running_in_docker() -> bool:
    # 允许测试覆盖（避免依赖真实 /.dockerenv）
    if os.getenv("FORCE_DOCKER_LOCALHOST_REWRITE") in ("1", "true", "TRUE", "yes", "YES"):
        return True
    return os.path.exists("/.dockerenv")


def rewrite_localhost_for_docker(url: str, *, docker_host: str = "host.docker.internal") -> str:
    """在 Docker 容器内把 localhost URL 重写为宿主机可达地址。

    场景：
    - Windows/本机测试常用 `http://localhost:PORT`
    - 但在容器里，localhost 指向容器自身，导致连通性失败
    """

    text = str(url or "").strip()
    if not text:
        return text

    try:
        parsed: SplitResult = urlsplit(text)
    except Exception:
        return text

    host = (parsed.hostname or "").strip().lower()
    if not host or host not in _LOCALHOST_HOSTS:
        return text

    if not _is_running_in_docker():
        return text

    port = parsed.port
    netloc = f"{docker_host}:{port}" if port is not None else docker_host
    # 保留 path/query/fragment（例如某些上游可能带 /api 前缀）
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

