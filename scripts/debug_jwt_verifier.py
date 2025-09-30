#!/usr/bin/env python3
"""调试JWT验证器。"""

import json
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import jwt
    from app.auth.jwt_verifier import get_jwt_verifier
    from app.settings.config import get_settings
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def debug_jwt_verification():
    """调试JWT验证过程。"""
    print("🔍 调试JWT验证器")
    print("=" * 50)

    # 从测试中获得的JWT token
    jwt_token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI5NmU2Y2E5LTk3MzMtNDgzZi1iNGJiLTcwMzliMzEwMmM5MiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3J5a2dsaXZyd3pjeWtoaG54d296LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI3N2MxNmY1My02NGQwLTQyNGItYjliZS1iOTQyYmI2ZTkyZmUiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTI1Nzk0LCJpYXQiOjE3NTkxMjIxOTQsImVtYWlsIjoidGVzdDE3NTkxMjE4MDVAZ3ltYnJvLmNsb3VkIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6InRlc3QxNzU5MTIxODA1QGd5bWJyby5jbG91ZCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6Ijc3YzE2ZjUzLTY0ZDAtNDI0Yi1iOWJlLWI5NDJiYjZlOTJmZSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im90cCIsInRpbWVzdGFtcCI6MTc1OTEyMjE5NH1dLCJzZXNzaW9uX2lkIjoiZjFhZjZlOGYtYWNmMC00ZDA0LWIzNzgtYzU2ZDNlYTkxNmIyIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.zS7NZRVU74CZLUzMFS5E1DITTUN5MbV_B9upO6L1JoSDvhHJYpdYjXLnf4RBuMoMLHHoxLLYR1dXaf63jwDrwg"

    print(f"🔑 JWT Token: {jwt_token[:50]}...")

    # 1. 测试JWT头部解析
    print("\n📋 步骤1: 解析JWT头部")
    try:
        header = jwt.get_unverified_header(jwt_token)
        print(f"✅ 头部解析成功:")
        print(json.dumps(header, indent=2))

        kid = header.get("kid")
        alg = header.get("alg")
        print(f"🔍 提取的字段:")
        print(f"   kid: {kid}")
        print(f"   alg: {alg}")

    except Exception as e:
        print(f"❌ 头部解析失败: {e}")
        return False

    # 2. 测试配置
    print("\n📋 步骤2: 检查配置")
    settings = get_settings()
    print(f"✅ 配置信息:")
    print(f"   JWKS URL: {settings.supabase_jwks_url}")
    print(f"   Issuer: {settings.supabase_issuer}")
    print(f"   Audience: {settings.supabase_audience}")
    print(f"   Project ID: {settings.supabase_project_id}")

    # 3. 测试JWKS获取
    print("\n📋 步骤3: 测试JWKS获取")
    try:
        verifier = get_jwt_verifier()
        cache = verifier._cache

        print(f"🔍 JWKS缓存配置:")
        print(f"   JWKS URL: {cache._jwks_url}")
        print(f"   TTL: {cache._ttl_seconds}秒")

        # 获取密钥
        keys = cache.get_keys()
        print(f"✅ 获取到 {len(keys)} 个密钥:")

        for i, key in enumerate(keys):
            key_kid = key.get("kid")
            key_alg = key.get("alg")
            key_kty = key.get("kty")
            print(f"   密钥 {i+1}: kid={key_kid}, alg={key_alg}, kty={key_kty}")

            # 检查是否匹配
            if key_kid == kid:
                print(f"   ✅ 找到匹配的密钥!")

        # 尝试获取特定密钥
        try:
            specific_key = cache.get_key(kid)
            print(f"✅ 成功获取kid={kid}的密钥")
        except Exception as e:
            print(f"❌ 获取特定密钥失败: {e}")
            return False

    except Exception as e:
        print(f"❌ JWKS获取失败: {e}")
        return False

    # 4. 测试完整验证
    print("\n📋 步骤4: 测试完整JWT验证")
    try:
        verifier = get_jwt_verifier()
        user = verifier.verify_token(jwt_token)

        print(f"✅ JWT验证成功!")
        print(f"   用户ID: {user.uid}")
        print(f"   邮箱: {user.claims.get('email')}")
        print(f"   角色: {user.claims.get('role')}")

        return True

    except Exception as e:
        print(f"❌ JWT验证失败: {e}")

        # 详细错误分析
        print(f"\n🔍 错误分析:")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误消息: {str(e)}")

        if hasattr(e, 'detail'):
            print(f"   详细信息: {e.detail}")

        # 尝试手动复现验证器的步骤来找到具体错误
        print(f"\n🔍 手动复现验证器步骤:")
        try:
            # 复制验证器的逻辑
            header = jwt.get_unverified_header(jwt_token)
            kid = header.get("kid")
            algorithm = header.get("alg")

            # 获取密钥
            cache = verifier._cache
            key_dict = cache.get_key(kid)

            # 创建公钥
            algorithm_cls = jwt.algorithms.get_default_algorithms()[algorithm]
            public_key = algorithm_cls.from_jwk(json.dumps(key_dict))

            # 设置验证参数
            settings = verifier._settings
            audience = (
                settings.required_audience
                or settings.supabase_audience
                or settings.supabase_project_id
            )

            issuers = verifier._expected_issuers()
            required_claims = ["iss", "sub", "exp", "iat", "nbf"]
            if audience:
                required_claims.append("aud")
            options = {
                "require": required_claims,
                "verify_aud": bool(audience),
            }

            print(f"   验证参数:")
            print(f"     算法: {algorithm}")
            print(f"     受众: {audience}")
            print(f"     签发者: {issuers}")
            print(f"     必需声明: {required_claims}")
            print(f"     选项: {options}")

            # 执行验证
            payload = jwt.decode(
                jwt_token,
                key=public_key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuers[0] if len(issuers) == 1 else None,
                leeway=settings.token_leeway_seconds,
                options=options,
            )

            print(f"   ✅ 手动复现验证成功!")

        except Exception as inner_e:
            print(f"   ❌ 手动复现也失败: {inner_e}")
            print(f"   内部错误类型: {type(inner_e).__name__}")

        return False


def test_manual_verification():
    """手动测试JWT验证步骤。"""
    print("\n📋 手动验证测试")
    print("=" * 50)

    jwt_token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI5NmU2Y2E5LTk3MzMtNDgzZi1iNGJiLTcwMzliMzEwMmM5MiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3J5a2dsaXZyd3pjeWtoaG54d296LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI3N2MxNmY1My02NGQwLTQyNGItYjliZS1iOTQyYmI2ZTkyZmUiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTI1Nzk0LCJpYXQiOjE3NTkxMjIxOTQsImVtYWlsIjoidGVzdDE3NTkxMjE4MDVAZ3ltYnJvLmNsb3VkIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6InRlc3QxNzU5MTIxODA1QGd5bWJyby5jbG91ZCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6Ijc3YzE2ZjUzLTY0ZDAtNDI0Yi1iOWJlLWI5NDJiYjZlOTJmZSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im90cCIsInRpbWVzdGFtcCI6MTc1OTEyMjE5NH1dLCJzZXNzaW9uX2lkIjoiZjFhZjZlOGYtYWNmMC00ZDA0LWIzNzgtYzU2ZDNlYTkxNmIyIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.zS7NZRVU74CZLUzMFS5E1DITTUN5MbV_B9upO6L1JoSDvhHJYpdYjXLnf4RBuMoMLHHoxLLYR1dXaf63jwDrwg"

    settings = get_settings()

    try:
        # 手动获取JWKS
        import httpx

        print("🔍 手动获取JWKS...")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(str(settings.supabase_jwks_url))
            jwks_data = response.json()

        print(f"✅ JWKS获取成功，包含 {len(jwks_data.get('keys', []))} 个密钥")

        # 解析JWT头部
        header = jwt.get_unverified_header(jwt_token)
        kid = header.get("kid")
        alg = header.get("alg")

        print(f"🔍 JWT头部: kid={kid}, alg={alg}")

        # 查找匹配的密钥
        matching_key = None
        for key in jwks_data.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break

        if not matching_key:
            print(f"❌ 未找到匹配的密钥 kid={kid}")
            return False

        print(f"✅ 找到匹配的密钥")
        print(f"   密钥类型: {matching_key.get('kty')}")
        print(f"   算法: {matching_key.get('alg')}")
        print(f"   用途: {matching_key.get('use')}")

        # 创建公钥
        algorithm_cls = jwt.algorithms.get_default_algorithms()[alg]
        public_key = algorithm_cls.from_jwk(json.dumps(matching_key))

        print(f"✅ 公钥创建成功: {type(public_key)}")

        # 验证JWT
        audience = settings.supabase_audience
        issuer = str(settings.supabase_issuer)

        print(f"🔍 验证参数:")
        print(f"   受众: {audience}")
        print(f"   签发者: {issuer}")

        payload = jwt.decode(
            jwt_token,
            key=public_key,
            algorithms=[alg],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={
                "require": ["iss", "sub", "exp", "iat", "aud"],
                "verify_aud": True,
            }
        )

        print(f"✅ 手动JWT验证成功!")
        print(f"   用户ID: {payload.get('sub')}")
        print(f"   邮箱: {payload.get('email')}")

        return True

    except Exception as e:
        print(f"❌ 手动验证失败: {e}")
        return False


def main():
    """主函数。"""
    print("🚀 JWT验证器调试工具\n")

    # 测试自动验证
    auto_success = debug_jwt_verification()

    # 测试手动验证
    manual_success = test_manual_verification()

    print("\n" + "=" * 50)
    print("📊 测试结果:")
    print(f"   自动验证: {'✅ 成功' if auto_success else '❌ 失败'}")
    print(f"   手动验证: {'✅ 成功' if manual_success else '❌ 失败'}")

    if auto_success and manual_success:
        print("\n🎉 JWT验证器工作正常!")
        return 0
    elif manual_success:
        print("\n⚠️  手动验证成功，但自动验证失败 - 可能是验证器配置问题")
        return 1
    else:
        print("\n❌ 验证失败 - 需要检查JWT token或配置")
        return 1


if __name__ == "__main__":
    exit(main())
