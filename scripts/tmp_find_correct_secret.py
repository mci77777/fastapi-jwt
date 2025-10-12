#!/usr/bin/env python3
"""尝试找到正确的 JWT Secret"""
import sys, os, json, base64
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import jwt

def main():
    # 1. 获取 SERVICE_ROLE_KEY
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not service_role_key:
        print("❌ SUPABASE_SERVICE_ROLE_KEY 未配置")
        return 1
    
    print(f"🔍 SERVICE_ROLE_KEY: {service_role_key[:50]}...")
    
    # 2. 解码 payload（不验证签名）
    payload = jwt.decode(service_role_key, options={"verify_signature": False})
    print(f"\n📋 Payload: {json.dumps(payload, indent=2)}")
    
    # 3. 尝试的密钥列表
    candidates = [
        ("SECRET_KEY", os.getenv('SECRET_KEY')),
        ("SUPABASE_JWT_SECRET", os.getenv('SUPABASE_JWT_SECRET')),
        ("PUBLISHABLE_KEY", os.getenv('PUBLISHABLE_KEY')),
    ]
    
    # 4. 从静态 JWK 提取 k 值
    supabase_jwk = os.getenv('SUPABASE_JWK')
    if supabase_jwk:
        jwk = json.loads(supabase_jwk)
        k_b64 = jwk.get('k', '')
        try:
            k_decoded = base64.urlsafe_b64decode(k_b64 + '==')
            candidates.append(("JWK.k (decoded)", k_decoded.decode('utf-8', errors='ignore')))
        except Exception as e:
            print(f"⚠️  JWK.k 解码失败: {e}")
    
    # 5. 逐个尝试验证
    print("\n🧪 尝试验证签名:")
    for name, secret in candidates:
        if not secret:
            continue
        try:
            jwt.decode(service_role_key, secret, algorithms=['HS256'], options={"verify_signature": True, "verify_aud": False, "verify_iss": False, "verify_exp": False})
            print(f"  ✅ {name}: 验证成功！")
            print(f"     密钥: {secret[:30]}...")
            return 0
        except jwt.InvalidSignatureError:
            print(f"  ❌ {name}: 签名不匹配")
        except Exception as e:
            print(f"  ⚠️  {name}: {e}")
    
    print("\n❌ 所有候选密钥均验证失败")
    print("\n💡 建议:")
    print("   1. 登录 Supabase Dashboard")
    print("   2. 进入 Settings → API → JWT Settings")
    print("   3. 复制 'JWT Secret' 字段")
    print("   4. 更新 .env 中的 SUPABASE_JWT_SECRET")
    return 1

if __name__ == '__main__':
    sys.exit(main())

