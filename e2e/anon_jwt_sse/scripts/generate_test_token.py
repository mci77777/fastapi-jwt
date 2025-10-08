#!/usr/bin/env python3
"""统一入口：获取匿名用户 JWT 并写入 artifacts/token.json。"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict

from anon_signin_enhanced import EnhancedAnonAuth


ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
TOKEN_FILE = ARTIFACTS_DIR / "token.json"


async def acquire_token(method: str, verify: bool) -> Dict[str, Any]:
    """根据指定方式获取匿名 Token，失败时自动回退。"""
    client = EnhancedAnonAuth()

    async def via_edge() -> Dict[str, Any]:
        return await client.get_token_via_edge_function()

    async def via_native() -> Dict[str, Any]:
        return await client.get_token_via_native_auth()

    if method == "edge":
        token_data = await via_edge()
    elif method == "native":
        token_data = await via_native()
    else:  # auto
        try:
            token_data = await via_edge()
        except Exception:
            token_data = await via_native()

    if verify:
        await client.verify_token_with_api(token_data["access_token"])

    return token_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取匿名 JWT 测试 Token")
    parser.add_argument(
        "--method",
        choices=["auto", "edge", "native"],
        default="auto",
        help="Token 获取方式：默认 auto 会优先尝试 Edge Function，再回退原生匿名登录",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="生成后立即调用 API 验证 Token 是否有效",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    token_data = asyncio.run(acquire_token(args.method, args.verify))

    # `EnhancedAnonAuth` 已经写入 token.json，这里只再次确认存在性，便于脚本输出。
    if TOKEN_FILE.exists():
        print(f"[OK] Token saved at: {TOKEN_FILE}")
    else:
        print("[WARN] Token file missing，可能需要检查权限或 Supabase 配置。")

    print(f"[INFO] Access token preview: {token_data['access_token'][:50]}...")


if __name__ == "__main__":
    main()
