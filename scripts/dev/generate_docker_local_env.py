#!/usr/bin/env python3
"""
从 `e2e/anon_jwt_sse/.env.local` 生成本地 Docker 启动用的 env（用于 docker compose --env-file）。

输出文件默认：.env.docker.local（根目录，已被 gitignore）

输入 SSOT（来自 e2e/.env.local）：
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - API_BASE / API_BASE_URL（可选）

输出（供 Dockerfile/compose 使用）：
  - VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY（前端构建期注入）
  - VITE_BASE_API=/api/v1
  - SUPABASE_ISSUER / SUPABASE_JWKS_URL（后端 JWT 校验）
  - JWT_AUDIENCE（默认 authenticated，可通过环境覆盖）
  - VITE_AUTH_MODE（默认 auto，可覆盖为 local/supabase）
  - WEB_PORT/API_PORT（默认 3101/9999，可覆盖）
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


def _parse_dotenv(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]
        data[key] = val
    return data


def _normalize_api_base(raw: str) -> str:
    v = (raw or "").strip().rstrip("/")
    if v.endswith("/api/v1"):
        v = v[: -len("/api/v1")]
    return v


def _derive_jwks_url(supabase_url: str) -> str:
    return supabase_url.rstrip("/") + "/.well-known/jwks.json"


def _derive_project_ref(supabase_url: str) -> Optional[str]:
    try:
        host = urlparse(supabase_url).hostname or ""
    except Exception:
        host = ""
    host = host.strip().lower()
    if host.endswith(".supabase.co"):
        return host.split(".supabase.co", 1)[0]
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    src = Path(os.getenv("E2E_ENV_PATH") or (repo_root / "e2e/anon_jwt_sse/.env.local"))
    dst = Path(os.getenv("DOCKER_ENV_PATH") or (repo_root / ".env.docker.local"))

    if not src.exists():
        print(f"Missing env file: {src}")
        return 2

    env = _parse_dotenv(src)
    supabase_url = (env.get("SUPABASE_URL") or "").strip().rstrip("/")
    supabase_anon_key = (env.get("SUPABASE_ANON_KEY") or "").strip()
    api_base = (env.get("API_BASE_URL") or env.get("API_BASE") or "").strip()

    if not supabase_url or not supabase_anon_key:
        print("Missing required keys in e2e env: SUPABASE_URL / SUPABASE_ANON_KEY")
        return 2

    issuer = supabase_url
    jwks_url = _derive_jwks_url(supabase_url)
    project_ref = _derive_project_ref(supabase_url) or ""

    api_base_norm = _normalize_api_base(api_base) if api_base else ""
    vite_api_url = api_base_norm or ""

    lines = [
        "# Auto-generated. DO NOT COMMIT.",
        "# Source of truth: e2e/anon_jwt_sse/.env.local",
        "",
        "VITE_AUTH_MODE=auto",
        f"VITE_SUPABASE_URL={supabase_url}",
        f"VITE_SUPABASE_ANON_KEY={supabase_anon_key}",
        "VITE_BASE_API=/api/v1",
        f"VITE_API_URL={vite_api_url}",
        "",
        f"SUPABASE_ISSUER={issuer}",
        f"SUPABASE_JWKS_URL={jwks_url}",
        "JWT_AUDIENCE=authenticated",
        "",
        "WEB_PORT=3101",
        "API_PORT=9999",
        "",
        f"# Derived (informational): SUPABASE_PROJECT_REF={project_ref}",
        "",
    ]

    dst.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {dst.relative_to(repo_root)} (keys: VITE_SUPABASE_*, SUPABASE_*, JWT_AUDIENCE, ports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
