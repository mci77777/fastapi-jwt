#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JWT 完整测试脚本：获取、验证、失效时间测试。

功能：
1. 从后端获取测试 JWT token（HS256）
2. 验证 token 有效性
3. 测试 token 失效时间（exp claim）
4. 支持真实 Supabase JWT 验证（ES256）

使用方法：
    # 测试后端生成的 HS256 token
    python scripts/test_jwt_complete.py

    # 验证真实 Supabase JWT（从浏览器获取）
    python scripts/test_jwt_complete.py --token "<your-token>"

    # 测试 token 失效
    python scripts/test_jwt_complete.py --test-expiry
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
import jwt
from dotenv import load_dotenv

load_dotenv()

from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings

# 配置
BASE_URL = "http://localhost:9999/api/v1"
FRONTEND_URL = "http://localhost:3101"


def print_section(title: str) -> None:
    """打印分节标题。"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def decode_token_without_verify(token: str) -> tuple[dict, dict]:
    """解码 JWT 但不验证签名。"""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        return header, payload
    except Exception as e:
        return {}, {"error": str(e)}


def get_test_token() -> str:
    """从后端获取测试 JWT token。"""
    print_section("1. 获取测试 JWT Token")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/access_token",
                json={"username": "admin", "password": "123456"},
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and "access_token" in data["data"]:
                token = data["data"]["access_token"]
            elif "access_token" in data:
                token = data["access_token"]
            else:
                raise ValueError(f"Unexpected response format: {data}")

            print("✅ Token 获取成功")
            print(f"   Token 长度: {len(token)}")
            print(f"   Token 预览: {token[:50]}...")
            return token

    except Exception as e:
        print(f"❌ Token 获取失败: {e}")
        sys.exit(1)


def analyze_token(token: str) -> None:
    """分析 JWT token 结构。"""
    print_section("2. 分析 Token 结构")

    header, payload = decode_token_without_verify(token)

    if "error" in payload:
        print(f"❌ Token 解码失败: {payload['error']}")
        return

    print("📋 JWT Header:")
    print(json.dumps(header, indent=2))

    print("\n📋 JWT Payload:")
    # 脱敏处理
    safe_payload = {**payload}
    if "sub" in safe_payload:
        sub = safe_payload["sub"]
        safe_payload["sub"] = sub[:20] + "..." if len(sub) > 20 else sub
    if "email" in safe_payload:
        email = safe_payload["email"]
        if "@" in email:
            safe_payload["email"] = email[:3] + "***@" + email.split("@")[1]

    print(json.dumps(safe_payload, indent=2))

    # 分析关键字段
    print("\n🔍 关键字段分析:")
    alg = header.get("alg")
    iss = payload.get("iss")
    aud = payload.get("aud")
    exp = payload.get("exp")
    iat = payload.get("iat")

    print(f"  算法 (alg): {alg}")
    if alg == "HS256":
        print("    ℹ️  HS256 = 对称密钥签名（测试 token）")
    elif alg == "ES256":
        print("    ℹ️  ES256 = 椭圆曲线数字签名（真实 Supabase JWT）")

    print(f"  签发者 (iss): {iss}")
    if "supabase.co/auth/v1" in str(iss):
        print("    ✅ 真实 Supabase Auth 签发")
    elif iss == "supabase":
        print("    ℹ️  Supabase 内部密钥格式")

    print(f"  受众 (aud): {aud}")

    if exp:
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        remaining = exp_dt - now
        print(f"  过期时间 (exp): {exp_dt.isoformat()}")
        print(f"    剩余时间: {remaining}")
        if remaining.total_seconds() < 0:
            print("    ⚠️  Token 已过期！")
        elif remaining.total_seconds() < 300:
            print("    ⚠️  Token 即将过期（<5分钟）")

    if iat:
        iat_dt = datetime.fromtimestamp(iat, tz=timezone.utc)
        print(f"  签发时间 (iat): {iat_dt.isoformat()}")


def verify_token(token: str) -> bool:
    """使用 JWTVerifier 验证 token。"""
    print_section("3. 验证 Token 签名")

    settings = get_settings()
    print("📋 JWT 配置:")
    print(f"  JWKS URL: {settings.supabase_jwks_url}")
    print(f"  允许的算法: {settings.jwt_allowed_algorithms}")
    print(f"  允许的 issuer: {settings.allowed_issuers}")
    print(f"  时钟偏移容忍: {settings.jwt_clock_skew_seconds}s")
    print(f"  要求 nbf: {settings.jwt_require_nbf}")

    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        print("\n✅ JWT 验证成功！")
        print(f"  用户 ID: {user.uid[:20]}...")
        print(f"  用户类型: {user.user_type}")
        print(f"  Claims 数量: {len(user.claims)}")

        # 显示部分 claims（脱敏）
        print("\n📋 用户 Claims（部分）:")
        for key in ["role", "email", "aud", "iss", "exp", "iat"]:
            if key in user.claims:
                val = user.claims[key]
                if key == "email" and isinstance(val, str) and "@" in val:
                    val = val[:3] + "***@" + val.split("@")[1]
                elif key in ["exp", "iat"]:
                    dt = datetime.fromtimestamp(val, tz=timezone.utc)
                    val = f"{val} ({dt.isoformat()})"
                print(f"  {key}: {val}")

        return True

    except Exception as e:
        print(f"\n❌ JWT 验证失败: {e}")
        import traceback

        print("\n详细错误信息:")
        traceback.print_exc()
        return False


def test_token_expiry() -> None:
    """测试 token 失效时间。"""
    print_section("4. 测试 Token 失效时间")

    print("⏳ 创建一个即将过期的 token（5秒后过期）...")

    settings = get_settings()
    if not settings.supabase_jwt_secret:
        print("❌ SUPABASE_JWT_SECRET 未配置，无法生成测试 token")
        return

    now = int(time.time())
    issuer = str(settings.supabase_issuer) if settings.supabase_issuer else "http://localhost:9999"

    payload = {
        "iss": issuer,
        "sub": "test-user-expiry",
        "aud": "authenticated",
        "exp": now + 5,  # 5秒后过期
        "iat": now,
        "email": "expiry-test@test.local",
        "role": "authenticated",
        "is_anonymous": False,
    }

    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    print("✅ Token 创建成功，将在 5 秒后过期")

    # 立即验证（应该成功）
    print("\n⏱️  立即验证（应该成功）...")
    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        print(f"✅ 验证成功: {user.uid}")
    except Exception as e:
        print(f"❌ 验证失败: {e}")

    # 等待 6 秒后验证（应该失败）
    print("\n⏱️  等待 6 秒后验证（应该失败）...")
    for i in range(6):
        print(f"  {i + 1}/6 秒...", end="\r")
        time.sleep(1)
    print()

    try:
        user = verifier.verify_token(token)
        print(f"⚠️  验证成功（不应该成功）: {user.uid}")
    except Exception as e:
        print(f"✅ 验证失败（符合预期）: {e}")


def main():
    parser = argparse.ArgumentParser(description="JWT 完整测试脚本")
    parser.add_argument("--token", help="要验证的 JWT token（可选，默认从后端获取）")
    parser.add_argument("--test-expiry", action="store_true", help="测试 token 失效时间")
    args = parser.parse_args()

    print("=" * 80)
    print("  JWT 完整测试脚本")
    print("=" * 80)

    if args.test_expiry:
        test_token_expiry()
        return 0

    # 获取或使用提供的 token
    if args.token:
        token = args.token
        print(f"\n使用提供的 token: {token[:50]}...")
    else:
        token = get_test_token()

    # 分析 token
    analyze_token(token)

    # 验证 token
    success = verify_token(token)

    # 总结
    print_section("测试总结")
    if success:
        print("✅ 所有测试通过")
        print("\n💡 提示:")
        print(f"  - 前端访问: {FRONTEND_URL}")
        print(f"  - 后端 API: {BASE_URL}")
        print("  - 使用 --test-expiry 测试 token 失效")
        return 0
    else:
        print("❌ 测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
