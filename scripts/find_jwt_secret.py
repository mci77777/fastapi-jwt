#!/usr/bin/env python3
"""
尝试找到正确的 JWT Secret
"""

import json
import os
import sys

import jwt

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


def try_jwt_secrets():
    """尝试不同的 JWT Secret"""
    print("🔍 寻找正确的 JWT Secret")
    print("=" * 50)
    
    settings = get_settings()
    service_key = settings.supabase_service_role_key
    
    # 候选密钥列表
    candidates = [
        "sb_secret_JZba0OSzvqEYVJADziEazg_HG3u57I3",  # SECRET_KEY
        "sb_publishable_YZnz-6LhPqUyBF9eEXZcbQ_QjRW5VnT",  # PUBLISHABLE_KEY
        "rykglivrwzcykhhnxwoz",  # Project ID
        "your-jwt-secret-here",  # 默认值
    ]
    
    # 从环境变量中获取更多候选
    env_candidates = [
        os.getenv("JWT_SECRET"),
        os.getenv("SUPABASE_JWT_SECRET"),
        os.getenv("SUPABASE_SECRET"),
    ]
    
    candidates.extend([c for c in env_candidates if c])
    
    print(f"🔑 测试 {len(candidates)} 个候选密钥...")
    
    for i, candidate in enumerate(candidates, 1):
        if not candidate:
            continue
            
        print(f"\n[{i}] 测试密钥: {candidate[:20]}...")
        
        try:
            # 尝试解码
            payload = jwt.decode(
                service_key,
                key=candidate,
                algorithms=['HS256'],
                options={
                    "verify_signature": True,
                    "verify_exp": False,
                    "verify_aud": False,
                    "verify_iss": False,
                }
            )
            
            print(f"    ✅ 成功! 找到正确的密钥")
            print(f"    📋 解码结果:")
            print(json.dumps(payload, indent=6))
            
            # 生成对应的 JWK
            import base64
            k = base64.urlsafe_b64encode(candidate.encode('utf-8')).decode('utf-8').rstrip('=')
            jwk = {
                "kty": "oct",
                "alg": "HS256",
                "use": "sig",
                "k": k
            }
            
            print(f"\n    🔧 对应的 JWK 配置:")
            jwk_json = json.dumps(jwk, separators=(',', ':'))
            print(f"    SUPABASE_JWK={jwk_json}")
            
            # 自动更新 .env 文件
            env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
            if os.path.exists(env_file):
                try:
                    with open(env_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 替换 SUPABASE_JWK
                    lines = content.split('\n')
                    for j, line in enumerate(lines):
                        if line.startswith('SUPABASE_JWK='):
                            lines[j] = f'SUPABASE_JWK={jwk_json}'
                            break
                    
                    with open(env_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    
                    print(f"    ✅ 已自动更新 .env 文件")
                    
                except Exception as e:
                    print(f"    ⚠️  无法更新 .env 文件: {e}")
            
            return candidate
            
        except jwt.InvalidSignatureError:
            print(f"    ❌ 签名验证失败")
        except Exception as e:
            print(f"    ❌ 解码失败: {e}")
    
    print(f"\n❌ 未找到正确的 JWT Secret")
    print(f"\n💡 建议:")
    print(f"   1. 检查 Supabase Dashboard > Settings > API > JWT Settings")
    print(f"   2. 确认使用的是正确的 JWT Secret（不是 API Key）")
    print(f"   3. 尝试重新生成 JWT Secret")
    
    return None


def main():
    """主函数"""
    secret = try_jwt_secrets()
    return 0 if secret else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
