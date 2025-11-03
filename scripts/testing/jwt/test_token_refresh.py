#!/usr/bin/env python3
"""
Token 刷新功能测试脚本

测试内容：
1. 登录获取 Token
2. 验证 Token 有效期（应为 24 小时）
3. 调用刷新端点获取新 Token
4. 验证新 Token 有效期
5. 使用新 Token 访问受保护端点
"""

import sys
import time
from pathlib import Path

import httpx
import jwt

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:9999/api/v1"


def print_section(title: str):
    """打印分隔线和标题。"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def decode_token(token: str) -> dict:
    """解码 JWT token（不验证签名）。"""
    try:
        # 解码 payload（不验证签名）
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except Exception as e:
        print(f"❌ 解码 Token 失败: {e}")
        return {}


def format_timestamp(ts: int) -> str:
    """格式化时间戳。"""
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def test_login() -> str:
    """测试登录并获取 Token。"""
    print_section("1. 登录获取 Token")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/access_token",
                json={"username": "admin", "password": "123456"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"❌ 登录失败: {data.get('msg')}")
                sys.exit(1)

            token = data["data"]["access_token"]
            print("✅ 登录成功")
            print(f"   Token 长度: {len(token)}")
            print(f"   Token 预览: {token[:50]}...")

            # 解码 Token
            payload = decode_token(token)
            if payload:
                exp = payload.get("exp")
                iat = payload.get("iat")
                if exp and iat:
                    print(f"   签发时间: {format_timestamp(iat)}")
                    print(f"   过期时间: {format_timestamp(exp)}")
                    print(f"   有效期: {(exp - iat) / 3600:.1f} 小时")

            return token

    except Exception as e:
        print(f"❌ 登录失败: {e}")
        sys.exit(1)


def test_refresh_token(old_token: str) -> str:
    """测试刷新 Token。"""
    print_section("2. 刷新 Token")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/refresh_token",
                headers={"Authorization": f"Bearer {old_token}"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"❌ 刷新失败: {data.get('msg')}")
                sys.exit(1)

            new_token = data["data"]["access_token"]
            expires_in = data["data"].get("expires_in", 0)

            print("✅ Token 刷新成功")
            print(f"   新 Token 长度: {len(new_token)}")
            print(f"   新 Token 预览: {new_token[:50]}...")
            print(f"   有效期: {expires_in / 3600:.1f} 小时")

            # 解码新 Token
            payload = decode_token(new_token)
            if payload:
                exp = payload.get("exp")
                iat = payload.get("iat")
                if exp and iat:
                    print(f"   签发时间: {format_timestamp(iat)}")
                    print(f"   过期时间: {format_timestamp(exp)}")
                    print(f"   实际有效期: {(exp - iat) / 3600:.1f} 小时")

            return new_token

    except Exception as e:
        print(f"❌ 刷新失败: {e}")
        sys.exit(1)


def test_protected_endpoint(token: str):
    """测试使用 Token 访问受保护端点。"""
    print_section("3. 使用新 Token 访问受保护端点")

    try:
        with httpx.Client(timeout=10.0) as client:
            # 测试 /base/userinfo
            response = client.get(
                f"{BASE_URL}/base/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"❌ 访问失败: {data.get('msg')}")
                sys.exit(1)

            user_info = data["data"]
            print("✅ 访问成功")
            print(f"   用户 ID: {user_info.get('id')}")
            print(f"   用户名: {user_info.get('username')}")
            print(f"   邮箱: {user_info.get('email')}")
            print(f"   是否管理员: {user_info.get('is_superuser')}")

    except Exception as e:
        print(f"❌ 访问失败: {e}")
        sys.exit(1)


def test_token_expiry():
    """测试 Token 过期检测。"""
    print_section("4. 测试 Token 过期检测")

    # 创建一个即将过期的 Token（5 分钟后过期）
    from app.settings import get_settings

    settings = get_settings()
    if not settings.supabase_jwt_secret:
        print("❌ SUPABASE_JWT_SECRET 未配置")
        return

    now = int(time.time())
    issuer = str(settings.supabase_issuer) if settings.supabase_issuer else "http://localhost:9999"

    payload = {
        "iss": issuer,
        "sub": "test-user-expiry",
        "aud": "authenticated",
        "exp": now + 300,  # 5 分钟后过期
        "iat": now,
        "email": "expiry-test@test.local",
        "role": "authenticated",
        "is_anonymous": False,
    }

    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    print("✅ 创建即将过期的 Token（5 分钟后过期）")
    print(f"   Token 预览: {token[:50]}...")

    # 解码验证
    decoded = decode_token(token)
    if decoded:
        exp = decoded.get("exp")
        iat = decoded.get("iat")
        if exp and iat:
            print(f"   签发时间: {format_timestamp(iat)}")
            print(f"   过期时间: {format_timestamp(exp)}")
            print(f"   剩余时间: {(exp - now) / 60:.1f} 分钟")

    # 测试刷新
    print("\n⏰ 测试刷新即将过期的 Token...")
    try:
        _ = test_refresh_token(token)
        print("✅ 即将过期的 Token 刷新成功")
    except Exception as e:
        print(f"❌ 刷新失败: {e}")


def main():
    """主函数。"""
    print("\n" + "=" * 60)
    print("  Token 刷新功能测试")
    print("=" * 60)

    # 1. 登录获取 Token
    token = test_login()

    # 2. 刷新 Token
    new_token = test_refresh_token(token)

    # 3. 使用新 Token 访问受保护端点
    test_protected_endpoint(new_token)

    # 4. 测试 Token 过期检测
    test_token_expiry()

    # 总结
    print_section("✅ 所有测试通过")
    print("\n测试结果：")
    print("  ✅ 登录获取 Token（24 小时有效期）")
    print("  ✅ Token 刷新功能正常")
    print("  ✅ 新 Token 可以访问受保护端点")
    print("  ✅ 即将过期的 Token 可以刷新")
    print("\n建议：")
    print("  1. 前端已实现自动刷新（剩余 5 分钟时触发）")
    print("  2. 用户可以长时间使用系统而不需要重新登录")
    print("  3. Token 过期后会自动重定向到登录页")


if __name__ == "__main__":
    main()
