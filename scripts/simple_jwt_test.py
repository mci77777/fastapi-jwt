#!/usr/bin/env python3
"""简单的 JWT 配置测试脚本。"""

import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("❌ 需要安装 httpx: pip install httpx")
    sys.exit(1)


def load_env_file():
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


def test_jwks_endpoint(jwks_url):
    """测试 JWKS 端点。"""
    if not jwks_url:
        print("❌ SUPABASE_JWKS_URL 未配置")
        return False
    
    try:
        print(f"🔍 测试 JWKS 端点: {jwks_url}")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(jwks_url)
            response.raise_for_status()
            
        jwks_data = response.json()
        print(f"✅ JWKS 端点可访问")
        print(f"📋 获取到 {len(jwks_data.get('keys', []))} 个密钥")
        
        # 显示密钥信息
        for i, key in enumerate(jwks_data.get('keys', [])):
            print(f"   密钥 {i+1}: kid={key.get('kid')}, alg={key.get('alg')}, kty={key.get('kty')}")
            
        return True
        
    except Exception as e:
        print(f"❌ JWKS 端点访问失败: {e}")
        return False


def check_configuration(env_vars):
    """检查配置完整性。"""
    print("🔍 检查配置完整性...")
    
    required_configs = [
        "SUPABASE_PROJECT_ID",
        "SUPABASE_JWKS_URL", 
        "SUPABASE_ISSUER",
        "SUPABASE_AUDIENCE",
        "SUPABASE_SERVICE_ROLE_KEY",
    ]
    
    all_good = True
    for name in required_configs:
        value = env_vars.get(name)
        if value:
            display_value = value[:50] + '...' if len(value) > 50 else value
            print(f"✅ {name}: {display_value}")
        else:
            print(f"❌ {name}: 未配置")
            all_good = False
    
    return all_good


def validate_issuer_audience(env_vars):
    """验证 issuer 和 audience 配置。"""
    project_id = env_vars.get("SUPABASE_PROJECT_ID")
    issuer = env_vars.get("SUPABASE_ISSUER")
    audience = env_vars.get("SUPABASE_AUDIENCE")
    
    print("🔍 验证 issuer 和 audience 配置...")
    
    expected_issuer = f"https://{project_id}.supabase.co/auth/v1"
    if issuer == expected_issuer:
        print(f"✅ ISSUER 配置正确: {issuer}")
    else:
        print(f"⚠️  ISSUER 可能不正确:")
        print(f"   当前值: {issuer}")
        print(f"   期望值: {expected_issuer}")
    
    if audience == "authenticated":
        print(f"✅ AUDIENCE 配置正确: {audience}")
    else:
        print(f"⚠️  AUDIENCE 建议设置为 'authenticated'，当前值: {audience}")


def main():
    """主函数。"""
    print("🚀 开始验证 Supabase JWT 配置...\n")
    
    # 加载环境变量
    env_vars = load_env_file()
    if not env_vars:
        print("❌ 无法加载 .env 文件")
        return 1
    
    # 检查配置
    config_ok = check_configuration(env_vars)
    print()
    
    # 验证 issuer 和 audience
    validate_issuer_audience(env_vars)
    print()
    
    # 测试 JWKS 端点
    jwks_ok = test_jwks_endpoint(env_vars.get("SUPABASE_JWKS_URL"))
    print()
    
    # 总结
    if config_ok and jwks_ok:
        print("🎉 所有测试通过！JWT 配置正确。")
        print("\n📝 下一步:")
        print("1. 启动 FastAPI 服务器")
        print("2. 使用有效的 Supabase JWT token 测试 API 端点")
        return 0
    else:
        print("❌ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
