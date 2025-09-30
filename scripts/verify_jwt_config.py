#!/usr/bin/env python3
"""验证 Supabase JWT 配置的脚本。"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from app.settings.config import get_settings


def test_jwks_endpoint():
    """测试 JWKS 端点是否可访问。"""
    settings = get_settings()
    
    if not settings.supabase_jwks_url:
        print("❌ SUPABASE_JWKS_URL 未配置")
        return False
    
    try:
        print(f"🔍 测试 JWKS 端点: {settings.supabase_jwks_url}")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(str(settings.supabase_jwks_url))
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


def test_jwt_verifier():
    """测试 JWT 验证器初始化。"""
    try:
        print("🔍 测试 JWT 验证器初始化...")
        
        from app.auth.jwt_verifier import get_jwt_verifier
        
        verifier = get_jwt_verifier()
        print("✅ JWT 验证器初始化成功")
        
        # 测试 JWKS 缓存
        try:
            keys = verifier._cache.get_keys()
            print(f"✅ JWKS 缓存工作正常，获取到 {len(keys)} 个密钥")
            return True
        except Exception as e:
            print(f"❌ JWKS 缓存测试失败: {e}")
            return False
            
    except Exception as e:
        print(f"❌ JWT 验证器初始化失败: {e}")
        return False


def check_configuration():
    """检查配置完整性。"""
    settings = get_settings()
    
    print("🔍 检查配置完整性...")
    
    required_configs = [
        ("SUPABASE_PROJECT_ID", settings.supabase_project_id),
        ("SUPABASE_JWKS_URL", settings.supabase_jwks_url),
        ("SUPABASE_ISSUER", settings.supabase_issuer),
        ("SUPABASE_AUDIENCE", settings.supabase_audience),
        ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
    ]
    
    all_good = True
    for name, value in required_configs:
        if value:
            print(f"✅ {name}: {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}")
        else:
            print(f"❌ {name}: 未配置")
            all_good = False
    
    return all_good


def main():
    """主函数。"""
    print("🚀 开始验证 Supabase JWT 配置...\n")
    
    # 检查配置
    config_ok = check_configuration()
    print()
    
    # 测试 JWKS 端点
    jwks_ok = test_jwks_endpoint()
    print()
    
    # 测试 JWT 验证器
    verifier_ok = test_jwt_verifier()
    print()
    
    # 总结
    if config_ok and jwks_ok and verifier_ok:
        print("🎉 所有测试通过！JWT 配置正确。")
        return 0
    else:
        print("❌ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
