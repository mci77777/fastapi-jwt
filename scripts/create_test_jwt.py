#!/usr/bin/env python3
"""创建测试用的 JWT token。"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

try:
    import httpx
    import jwt
except ImportError:
    print("❌ 需要安装依赖: pip install httpx pyjwt")
    exit(1)


def load_env_file() -> Dict[str, str]:
    """加载 .env 文件。"""
    env_file = Path(__file__).parent.parent / ".env"
    env_vars = {}
    
    if not env_file.exists():
        print(f"❌ .env 文件不存在: {env_file}")
        return env_vars
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def get_jwks_keys(jwks_url: str) -> Optional[list]:
    """获取 JWKS 密钥。"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(jwks_url)
            if response.status_code == 200:
                jwks_data = response.json()
                return jwks_data.get("keys", [])
    except Exception as e:
        print(f"❌ 获取 JWKS 失败: {e}")
    return None


def create_mock_jwt_token(env_vars: Dict[str, str]) -> Optional[str]:
    """创建一个模拟的 JWT token 用于测试。"""
    
    # 获取 JWKS 密钥
    jwks_url = env_vars.get("SUPABASE_JWKS_URL")
    if not jwks_url:
        print("❌ SUPABASE_JWKS_URL 未配置")
        return None
    
    keys = get_jwks_keys(jwks_url)
    if not keys:
        print("❌ 无法获取 JWKS 密钥")
        return None
    
    # 使用第一个密钥的 kid
    first_key = keys[0]
    kid = first_key.get("kid")
    
    if not kid:
        print("❌ JWKS 密钥没有 kid")
        return None
    
    print(f"🔑 使用密钥 ID: {kid}")
    
    # 创建 JWT payload
    now = int(time.time())
    user_id = str(uuid.uuid4())
    
    payload = {
        "iss": env_vars.get("SUPABASE_ISSUER"),
        "sub": user_id,
        "aud": env_vars.get("SUPABASE_AUDIENCE"),
        "exp": now + 3600,  # 1小时后过期
        "iat": now,
        "email": f"test-{user_id[:8]}@test.local",
        "role": "authenticated",
        "user_metadata": {},
        "app_metadata": {
            "provider": "email",
            "providers": ["email"]
        }
    }
    
    # 注意：这里我们无法真正签名，因为我们没有私钥
    # 但我们可以创建一个结构正确的 token 用于测试
    print("⚠️  注意：这是一个模拟 token，无法通过真实验证")
    print(f"📋 Payload: {json.dumps(payload, indent=2)}")
    
    return None


def try_auth_api_signup(env_vars: Dict[str, str]) -> Optional[str]:
    """尝试通过 Auth API 注册用户。"""
    supabase_url = env_vars.get("SUPABASE_URL")
    anon_key = env_vars.get("SUPABASE_ANON_KEY")
    
    if not supabase_url or not anon_key:
        print("❌ SUPABASE_URL 或 SUPABASE_ANON_KEY 未配置")
        return None
    
    # 尝试不同的邮箱格式
    email_formats = [
        f"test{int(time.time())}@gmail.com",
        f"test{int(time.time())}@example.org",
        f"testuser{uuid.uuid4().hex[:8]}@test.com"
    ]
    
    for test_email in email_formats:
        try:
            print(f"🔍 尝试注册用户: {test_email}")
            
            with httpx.Client(timeout=30.0) as client:
                # 注册
                signup_response = client.post(
                    f"{supabase_url}/auth/v1/signup",
                    headers={
                        "apikey": anon_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": test_email,
                        "password": "TestPassword123!",
                        "data": {}
                    }
                )
                
                print(f"   注册状态码: {signup_response.status_code}")
                
                if signup_response.status_code in [200, 201]:
                    signup_data = signup_response.json()
                    print("✅ 注册成功")
                    
                    # 如果注册成功，尝试登录
                    login_response = client.post(
                        f"{supabase_url}/auth/v1/token?grant_type=password",
                        headers={
                            "apikey": anon_key,
                            "Content-Type": "application/json"
                        },
                        json={
                            "email": test_email,
                            "password": "TestPassword123!"
                        }
                    )
                    
                    print(f"   登录状态码: {login_response.status_code}")
                    
                    if login_response.status_code == 200:
                        login_data = login_response.json()
                        access_token = login_data.get("access_token")
                        
                        if access_token:
                            print("✅ 获取 JWT token 成功")
                            user_id = login_data.get("user", {}).get("id")
                            print(f"🆔 用户 ID: {user_id}")
                            print(f"📧 用户邮箱: {test_email}")
                            return access_token
                        else:
                            print("❌ 登录响应中没有 access_token")
                    else:
                        print(f"❌ 登录失败: {login_response.text}")
                else:
                    print(f"❌ 注册失败: {signup_response.text}")
                    
        except Exception as e:
            print(f"❌ 尝试 {test_email} 失败: {e}")
            continue
    
    return None


def main():
    """主函数。"""
    print("🚀 创建测试用的 JWT token\n")
    
    # 加载环境变量
    env_vars = load_env_file()
    if not env_vars:
        print("❌ 无法加载 .env 文件")
        return 1
    
    print("方法 1: 尝试通过 Auth API 创建真实用户")
    print("=" * 50)
    
    jwt_token = try_auth_api_signup(env_vars)
    
    if jwt_token:
        print(f"\n🎉 成功获取 JWT token!")
        print(f"🔑 Token: {jwt_token[:50]}...")
        
        # 保存到文件
        token_file = Path(__file__).parent / "test_jwt_token.txt"
        with open(token_file, 'w') as f:
            f.write(jwt_token)
        print(f"💾 Token 已保存到: {token_file}")
        
        return 0
    else:
        print("\n❌ 无法获取真实的 JWT token")
        
        print("\n方法 2: 分析 JWKS 密钥结构")
        print("=" * 50)
        create_mock_jwt_token(env_vars)
        
        print("\n💡 建议:")
        print("1. 在 Supabase Dashboard 中手动创建一个测试用户")
        print("2. 使用前端应用登录获取真实的 JWT token")
        print("3. 或者暂时禁用 JWT 验证进行 API 测试")
        
        return 1


if __name__ == "__main__":
    exit(main())
