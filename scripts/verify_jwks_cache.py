#!/usr/bin/env python3
"""验证 JWKS 缓存和 JWT 验证器功能"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.auth.jwt_verifier import get_jwt_verifier, JWKSCache
from app.settings.config import get_settings


def test_jwks_cache():
    """测试 JWKS 缓存功能"""
    print("=" * 60)
    print("测试 1: JWKS 缓存功能")
    print("=" * 60)
    
    settings = get_settings()
    
    # 显示配置
    print(f"\n配置信息:")
    print(f"  JWKS URL: {settings.supabase_jwks_url}")
    print(f"  静态 JWK: {'已配置' if settings.supabase_jwk else '未配置'}")
    print(f"  缓存 TTL: {settings.jwks_cache_ttl_seconds} 秒")
    print(f"  HTTP 超时: {settings.http_timeout_seconds} 秒")
    
    # 创建缓存实例
    cache = JWKSCache(
        jwks_url=str(settings.supabase_jwks_url) if settings.supabase_jwks_url else None,
        static_jwk=settings.supabase_jwk,
        ttl_seconds=settings.jwks_cache_ttl_seconds,
        timeout_seconds=settings.http_timeout_seconds,
    )
    
    # 测试获取密钥
    try:
        keys = cache.get_keys()
        print(f"\n成功获取 {len(keys)} 个密钥:")
        for i, key in enumerate(keys):
            print(f"  密钥 {i+1}:")
            print(f"    kid: {key.get('kid', 'N/A')}")
            print(f"    alg: {key.get('alg', 'N/A')}")
            print(f"    kty: {key.get('kty', 'N/A')}")
            print(f"    use: {key.get('use', 'N/A')}")
        return True
    except Exception as e:
        print(f"\n获取密钥失败: {e}")
        return False


def test_jwt_verifier_config():
    """测试 JWT 验证器配置"""
    print("\n" + "=" * 60)
    print("测试 2: JWT 验证器配置")
    print("=" * 60)
    
    settings = get_settings()
    
    print(f"\nJWT 硬化配置:")
    print(f"  时钟偏移容忍: {settings.jwt_clock_skew_seconds} 秒")
    print(f"  最大未来 iat: {settings.jwt_max_future_iat_seconds} 秒")
    print(f"  要求 nbf: {settings.jwt_require_nbf}")
    print(f"  允许的算法: {', '.join(settings.jwt_allowed_algorithms)}")
    
    print(f"\nSupabase 配置:")
    print(f"  项目 ID: {settings.supabase_project_id}")
    print(f"  Issuer: {settings.supabase_issuer}")
    print(f"  Audience: {settings.supabase_audience}")
    
    # 验证必需配置
    required_configs = [
        ("SUPABASE_PROJECT_ID", settings.supabase_project_id),
        ("SUPABASE_ISSUER", settings.supabase_issuer),
        ("SUPABASE_AUDIENCE", settings.supabase_audience),
    ]
    
    all_configured = True
    print(f"\n必需配置检查:")
    for name, value in required_configs:
        if value:
            print(f"  {name}: 已配置")
        else:
            print(f"  {name}: 未配置")
            all_configured = False
    
    return all_configured


def test_jwt_verifier_instance():
    """测试 JWT 验证器实例化"""
    print("\n" + "=" * 60)
    print("测试 3: JWT 验证器实例化")
    print("=" * 60)
    
    try:
        verifier = get_jwt_verifier()
        print("\n成功创建 JWT 验证器实例")
        print(f"  缓存实例: {type(verifier._cache).__name__}")
        print(f"  设置实例: {type(verifier._settings).__name__}")
        return True
    except Exception as e:
        print(f"\n创建验证器失败: {e}")
        return False


def test_token_validation():
    """测试 Token 验证（使用测试 token）"""
    print("\n" + "=" * 60)
    print("测试 4: Token 验证")
    print("=" * 60)
    
    # 检查是否有测试 token
    token_file = project_root / "e2e" / "anon_jwt_sse" / "artifacts" / "token.json"
    
    if not token_file.exists():
        print(f"\n跳过: 未找到测试 token 文件")
        print(f"  路径: {token_file}")
        return None
    
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        access_token = token_data.get('access_token')
        if not access_token:
            print("\ntoken.json 中未找到 access_token")
            return None
        
        print(f"\n找到测试 token (长度: {len(access_token)})")
        
        # 尝试验证
        verifier = get_jwt_verifier()
        try:
            user = verifier.verify_token(access_token)
            print(f"\nToken 验证成功:")
            print(f"  用户 ID: {user.uid}")
            print(f"  用户类型: {user.user_type}")
            print(f"  是否匿名: {user.is_anonymous}")
            print(f"  Claims 数量: {len(user.claims)}")
            return True
        except Exception as e:
            print(f"\nToken 验证失败: {e}")
            return False
            
    except Exception as e:
        print(f"\n读取 token 文件失败: {e}")
        return None


def main():
    """主函数"""
    print("\nJWKS 缓存和 JWT 验证器功能验证")
    print("=" * 60)
    
    results = {
        "JWKS 缓存": test_jwks_cache(),
        "JWT 配置": test_jwt_verifier_config(),
        "验证器实例": test_jwt_verifier_instance(),
        "Token 验证": test_token_validation(),
    }
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for test_name, result in results.items():
        if result is True:
            status = "通过"
        elif result is False:
            status = "失败"
        else:
            status = "跳过"
        print(f"  {test_name}: {status}")
    
    # 判断整体结果
    failed_tests = [name for name, result in results.items() if result is False]
    
    if failed_tests:
        print(f"\n有 {len(failed_tests)} 个测试失败")
        return 1
    else:
        print(f"\n所有测试通过或跳过")
        return 0


if __name__ == "__main__":
    sys.exit(main())

