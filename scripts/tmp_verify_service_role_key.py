#!/usr/bin/env python3
"""验证 Supabase SERVICE_ROLE_KEY 是否能通过 JWT 验证"""
import sys, os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.auth.jwt_verifier import get_jwt_verifier
from app.settings.config import get_settings

def main():
    s = get_settings()
    
    if not s.supabase_service_role_key:
        print("❌ SUPABASE_SERVICE_ROLE_KEY 未配置")
        return 1
    
    token = s.supabase_service_role_key
    print(f"🧪 测试 SERVICE_ROLE_KEY: {token[:50]}...")
    
    verifier = get_jwt_verifier()
    try:
        user = verifier.verify_token(token)
        print(f"✅ 验证成功！")
        print(f"   uid: {user.uid}")
        print(f"   user_type: {user.user_type}")
        print(f"   claims: {user.claims}")
        return 0
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

