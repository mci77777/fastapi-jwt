#!/usr/bin/env python3
"""分析 JWT token 来源和类型"""
import sys
import json
import jwt

def analyze_token(token_str):
    """分析 JWT token"""
    print("=" * 80)
    print("JWT Token 分析")
    print("=" * 80)
    
    # 1. 解码 header
    print("\n[1] Token Header:")
    try:
        header = jwt.get_unverified_header(token_str)
        print(json.dumps(header, indent=2))
        
        alg = header.get('alg')
        kid = header.get('kid')
        
        print(f"\n  算法 (alg): {alg}")
        if alg == 'HS256':
            print("    → 对称密钥签名（HMAC with SHA-256）")
            print("    → 通常用于后端生成的测试 token")
        elif alg == 'ES256':
            print("    → 非对称密钥签名（ECDSA with SHA-256）")
            print("    → 通常用于 Supabase Auth 签发的真实 token")
        elif alg == 'RS256':
            print("    → 非对称密钥签名（RSA with SHA-256）")
            print("    → 通常用于 OAuth2/OpenID Connect")
        
        print(f"  密钥 ID (kid): {kid}")
        if kid:
            print("    → 有 kid，可能使用 JWKS 验证")
        else:
            print("    → 无 kid，可能使用静态密钥验证")
            
    except Exception as e:
        print(f"  ❌ 解码 header 失败: {e}")
        return False
    
    # 2. 解码 payload
    print("\n[2] Token Payload:")
    try:
        payload = jwt.decode(token_str, options={"verify_signature": False})
        
        # 脱敏处理
        safe_payload = {**payload}
        if 'sub' in safe_payload and len(safe_payload['sub']) > 20:
            safe_payload['sub'] = safe_payload['sub'][:20] + '...'
        if 'email' in safe_payload and '@' in safe_payload['email']:
            email = safe_payload['email']
            safe_payload['email'] = email[:3] + '***@' + email.split('@')[1]
        
        print(json.dumps(safe_payload, indent=2))
        
        # 3. 分析关键字段
        print("\n[3] 关键字段分析:")
        
        iss = payload.get('iss')
        print(f"  签发者 (iss): {iss}")
        if 'supabase.co/auth/v1' in str(iss):
            print("    → Supabase Auth 签发")
        elif iss == 'supabase':
            print("    → Supabase 内部密钥（ANON_KEY/SERVICE_ROLE_KEY）")
        elif 'localhost' in str(iss) or 'test' in str(iss):
            print("    → 本地测试环境签发")
        
        sub = payload.get('sub')
        print(f"  用户 ID (sub): {sub}")
        if 'test-user-' in str(sub):
            print("    → 测试用户（由后端生成）")
        else:
            print("    → 真实用户 ID")
        
        aud = payload.get('aud')
        print(f"  受众 (aud): {aud}")
        
        role = payload.get('role')
        print(f"  角色 (role): {role}")
        
        is_anon = payload.get('is_anonymous')
        print(f"  匿名用户: {is_anon}")
        
        # 4. 判断 token 类型
        print("\n[4] Token 类型判断:")
        
        token_type = "未知"
        source = "未知"
        
        if alg == 'HS256' and 'test-user-' in str(sub):
            token_type = "测试 Token"
            source = "Dashboard 后端 (/api/v1/base/access_token)"
            print(f"  ✅ 类型: {token_type}")
            print(f"  ✅ 来源: {source}")
            print(f"  ✅ 用途: 本地开发测试")
            print(f"  ✅ 签名方式: 对称密钥（SUPABASE_JWT_SECRET）")
        elif alg == 'ES256' and kid:
            token_type = "真实 Supabase JWT"
            source = "Supabase Auth 服务"
            print(f"  ✅ 类型: {token_type}")
            print(f"  ✅ 来源: {source}")
            print(f"  ✅ 用途: 生产环境用户认证")
            print(f"  ✅ 签名方式: 非对称密钥（JWKS）")
        elif alg == 'HS256' and iss == 'supabase':
            token_type = "Supabase 内部密钥"
            source = "ANON_KEY 或 SERVICE_ROLE_KEY"
            print(f"  ✅ 类型: {token_type}")
            print(f"  ✅ 来源: {source}")
            print(f"  ✅ 用途: 服务端 API 调用")
            print(f"  ✅ 签名方式: 对称密钥（项目密钥）")
        else:
            print(f"  ⚠️  类型: {token_type}")
            print(f"  ⚠️  来源: {source}")
        
        # 5. 时间信息
        print("\n[5] 时间信息:")
        import time
        
        iat = payload.get('iat')
        if iat:
            iat_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(iat))
            print(f"  签发时间 (iat): {iat_time}")
        
        exp = payload.get('exp')
        if exp:
            exp_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))
            remaining = exp - int(time.time())
            print(f"  过期时间 (exp): {exp_time}")
            if remaining > 0:
                print(f"  剩余时间: {remaining // 60} 分钟")
            else:
                print(f"  ⚠️  Token 已过期！")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 解码 payload 失败: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/analyze_jwt.py <jwt_token>")
        print("\n示例:")
        print('  python scripts/analyze_jwt.py "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."')
        return 1
    
    token = sys.argv[1]
    success = analyze_token(token)
    
    print("\n" + "=" * 80)
    if success:
        print("✅ 分析完成")
    else:
        print("❌ 分析失败")
    print("=" * 80)
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())

