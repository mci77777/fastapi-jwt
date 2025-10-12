#!/usr/bin/env python3
"""验证真实的 Supabase ES256 JWT token"""
import sys, os, json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import jwt
from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings

def decode_without_verify(token: str):
    """解码 JWT 但不验证签名"""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        return header, payload
    except Exception as e:
        return None, {"error": str(e)}

def main():
    # 1. 从命令行参数或环境变量获取 token
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = os.getenv('TEST_JWT_TOKEN')
    
    if not token:
        print("❌ 未提供 JWT token")
        print("\n使用方法:")
        print("  python scripts/tmp_verify_es256_jwt.py <token>")
        print("  或设置环境变量: TEST_JWT_TOKEN=<token>")
        print("\n获取 token 的方法:")
        print("  1. 打开浏览器控制台（http://localhost:3101）")
        print("  2. 执行: JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value")
        print("  3. 复制完整的 token 字符串")
        return 1
    
    print("=" * 80)
    print("Supabase ES256 JWT 验证测试")
    print("=" * 80)
    
    # 2. 解码 token（不验证签名）
    print(f"\n[1] Token 预览: {token[:50]}...")
    header, payload = decode_without_verify(token)
    
    if not header:
        print(f"❌ Token 解码失败: {payload.get('error')}")
        return 1
    
    print(f"\n[2] JWT Header:")
    print(json.dumps(header, indent=2))
    
    print(f"\n[3] JWT Payload:")
    # 脱敏处理
    safe_payload = {**payload}
    if 'sub' in safe_payload:
        safe_payload['sub'] = safe_payload['sub'][:20] + '...' if len(safe_payload['sub']) > 20 else safe_payload['sub']
    if 'email' in safe_payload:
        email = safe_payload['email']
        safe_payload['email'] = email[:3] + '***@' + email.split('@')[1] if '@' in email else '***'
    print(json.dumps(safe_payload, indent=2))
    
    # 3. 验证关键字段
    print(f"\n[4] 关键字段验证:")
    alg = header.get('alg')
    iss = payload.get('iss')
    aud = payload.get('aud')
    kid = header.get('kid')
    
    print(f"  算法 (alg): {alg}")
    if alg == 'ES256':
        print("    ✅ 使用 ES256 算法（椭圆曲线数字签名）")
    elif alg == 'HS256':
        print("    ⚠️  使用 HS256 算法（对称密钥）- 这可能是测试 token")
    else:
        print(f"    ⚠️  使用 {alg} 算法")
    
    print(f"  签发者 (iss): {iss}")
    if 'supabase.co/auth/v1' in str(iss):
        print("    ✅ 真实 Supabase Auth 签发")
    elif iss == 'supabase':
        print("    ⚠️  内部密钥格式（ANON_KEY/SERVICE_ROLE_KEY）")
    
    print(f"  受众 (aud): {aud}")
    if aud == 'authenticated':
        print("    ✅ 已认证用户")
    
    print(f"  密钥 ID (kid): {kid}")
    
    # 4. 使用 JWTVerifier 验证
    print(f"\n[5] 使用 JWTVerifier 验证签名:")
    s = get_settings()
    print(f"  JWKS URL: {s.supabase_jwks_url}")
    print(f"  允许的算法: {s.jwt_allowed_algorithms}")
    print(f"  允许的 issuer: {s.supabase_issuer}, {s.allowed_issuers}")
    
    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        print(f"\n✅ JWT 验证成功！")
        print(f"  用户 ID: {user.uid[:20]}...")
        print(f"  用户类型: {user.user_type}")
        print(f"  Claims 数量: {len(user.claims)}")
        
        # 显示部分 claims（脱敏）
        print(f"\n[6] 用户 Claims（部分）:")
        for key in ['role', 'email', 'aud', 'iss', 'exp', 'iat']:
            if key in user.claims:
                val = user.claims[key]
                if key == 'email' and isinstance(val, str) and '@' in val:
                    val = val[:3] + '***@' + val.split('@')[1]
                print(f"  {key}: {val}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ JWT 验证失败: {e}")
        import traceback
        print("\n详细错误信息:")
        traceback.print_exc()
        
        print("\n💡 可能的原因:")
        if alg != 'ES256':
            print("  - Token 不是 ES256 签名（可能是测试 token）")
        if 'supabase.co/auth/v1' not in str(iss):
            print("  - Token 不是真实 Supabase Auth 签发")
        if not kid:
            print("  - Token 缺少 kid（密钥 ID）")
        print("  - JWKS 端点无法访问或密钥不匹配")
        print("  - Token 已过期")
        
        return 1

if __name__ == '__main__':
    sys.exit(main())

