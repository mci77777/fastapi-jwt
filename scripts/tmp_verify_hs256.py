#!/usr/bin/env python3
import sys, time
from pathlib import Path

# ensure project on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import jwt
from app.settings.config import get_settings
from app.auth.jwt_verifier import get_jwt_verifier

def main():
    s = get_settings()
    if not s.supabase_jwt_secret:
        print("❌ SUPABASE_JWT_SECRET 未配置，无法生成测试 token")
        return 1
    iss = (str(s.supabase_issuer).rstrip('/') if s.supabase_issuer else 'https://example.supabase.co/auth/v1')
    aud = s.supabase_audience or 'authenticated'
    now = int(time.time())
    payload = {
        'iss': iss,
        'aud': aud,
        'sub': 'test-user-admin',
        'email': 'test@example.com',
        'role': 'authenticated',
        'iat': now,
        'exp': now + 3600,
    }
    token = jwt.encode(payload, s.supabase_jwt_secret, algorithm='HS256')
    print(f"🧪 生成测试 token: {token[:50]}...")

    verifier = get_jwt_verifier()
    user = verifier.verify_token(token)
    print(f"✅ 验证成功 uid={user.uid} user_type={user.user_type}")
    return 0

if __name__ == '__main__':
    sys.exit(main())

