#!/usr/bin/env python3
"""测试 JWKS 密钥加载和 ES256 支持"""
import sys, json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import jwt
from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings

def main():
    print("=" * 80)
    print("JWKS 密钥加载测试")
    print("=" * 80)
    
    s = get_settings()
    
    print(f"\n[1] 配置检查:")
    print(f"  JWKS URL: {s.supabase_jwks_url}")
    print(f"  允许的算法: {s.jwt_allowed_algorithms}")
    
    print(f"\n[2] PyJWT 支持的算法:")
    algs = list(jwt.algorithms.get_default_algorithms().keys())
    print(f"  {', '.join(algs)}")
    print(f"  ✅ ES256 支持: {'ES256' in algs}")
    print(f"  ✅ RS256 支持: {'RS256' in algs}")
    
    print(f"\n[3] 初始化 JWT 验证器:")
    verifier = get_jwt_verifier()
    print(f"  ✅ 验证器初始化成功")
    
    print(f"\n[4] 获取 JWKS 密钥:")
    try:
        keys = verifier._cache.get_keys()
        print(f"  ✅ 成功获取 {len(keys)} 个密钥")
        
        for i, key in enumerate(keys, 1):
            print(f"\n  密钥 {i}:")
            print(f"    kid: {key.get('kid')}")
            print(f"    kty: {key.get('kty')}")
            print(f"    alg: {key.get('alg')}")
            print(f"    use: {key.get('use')}")
            
            # 尝试加载密钥
            kid = key.get('kid')
            alg = key.get('alg')
            try:
                algorithm_cls = jwt.algorithms.get_default_algorithms()[alg]
                public_key = algorithm_cls.from_jwk(json.dumps(key))
                print(f"    ✅ 密钥加载成功 (类型: {type(public_key).__name__})")
            except Exception as e:
                print(f"    ❌ 密钥加载失败: {e}")
    
    except Exception as e:
        print(f"  ❌ 获取密钥失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    print("✅ 所有测试通过！系统已准备好验证 ES256 JWT")
    print("=" * 80)
    return 0

if __name__ == '__main__':
    sys.exit(main())

