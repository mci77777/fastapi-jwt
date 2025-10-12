#!/usr/bin/env python3
"""解码 Supabase 密钥以验证 issuer 和 audience"""
import sys, json, base64
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import jwt
from app.settings.config import get_settings

def decode_jwt_without_verify(token: str):
    """不验证签名，仅解码 JWT"""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        return header, payload
    except Exception as e:
        return None, {"error": str(e)}

def main():
    s = get_settings()
    
    print("=" * 80)
    print("Supabase 配置分析")
    print("=" * 80)
    
    # 1. 解码 ANON_KEY
    if s.supabase_anon_key:
        print("\n[1] SUPABASE_ANON_KEY 解码:")
        h, p = decode_jwt_without_verify(s.supabase_anon_key)
        print(f"  Header: {json.dumps(h, indent=2)}")
        print(f"  Payload: {json.dumps(p, indent=2)}")
    
    # 2. 解码 SERVICE_ROLE_KEY
    if s.supabase_service_role_key:
        print("\n[2] SUPABASE_SERVICE_ROLE_KEY 解码:")
        h, p = decode_jwt_without_verify(s.supabase_service_role_key)
        print(f"  Header: {json.dumps(h, indent=2)}")
        print(f"  Payload: {json.dumps(p, indent=2)}")
    
    # 3. 当前配置
    print("\n[3] 当前 .env 配置:")
    print(f"  SUPABASE_ISSUER: {s.supabase_issuer}")
    print(f"  SUPABASE_AUDIENCE: {s.supabase_audience}")
    print(f"  SUPABASE_PROJECT_ID: {s.supabase_project_id}")
    print(f"  SUPABASE_JWT_SECRET: {s.supabase_jwt_secret[:20]}... (前20字符)")
    
    # 4. 解码静态 JWK 的 k 值
    if s.supabase_jwk:
        print("\n[4] 静态 JWK 配置:")
        jwk = json.loads(s.supabase_jwk)
        print(f"  kty: {jwk.get('kty')}")
        print(f"  alg: {jwk.get('alg')}")
        print(f"  use: {jwk.get('use')}")
        k_b64 = jwk.get('k', '')
        # 解码 base64url 的 k 值
        try:
            k_decoded = base64.urlsafe_b64decode(k_b64 + '==')  # 补齐 padding
            print(f"  k (decoded): {k_decoded.decode('utf-8', errors='ignore')}")
        except Exception as e:
            print(f"  k (decode error): {e}")
    
    # 5. 对比分析
    print("\n[5] 配置一致性检查:")
    if s.supabase_anon_key:
        _, anon_payload = decode_jwt_without_verify(s.supabase_anon_key)
        anon_iss = anon_payload.get('iss', '')
        anon_ref = anon_payload.get('ref', '')
        
        print(f"  ✓ ANON_KEY issuer: {anon_iss}")
        print(f"  ✓ ANON_KEY ref: {anon_ref}")
        print(f"  ✓ 配置的 ISSUER: {s.supabase_issuer}")
        
        # 检查是否匹配
        if anon_iss == 'supabase':
            print(f"  ⚠️  ANON_KEY 的 iss='supabase' (内部密钥，非真实 Supabase Auth)")
            print(f"  ⚠️  真实 issuer 应为: https://{anon_ref}.supabase.co/auth/v1")
            print(f"  ⚠️  当前配置的 ISSUER 正确: {s.supabase_issuer}")
        
        if str(s.supabase_issuer).rstrip('/') == anon_iss.rstrip('/'):
            print("  ✅ ISSUER 配置匹配")
        else:
            print(f"  ❌ ISSUER 不匹配！")
            print(f"     期望: {anon_iss}")
            print(f"     实际: {s.supabase_issuer}")
    
    print("\n" + "=" * 80)
    return 0

if __name__ == '__main__':
    sys.exit(main())

