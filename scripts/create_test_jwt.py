"""创建测试 JWT token（使用 Supabase JWT Secret）。"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import jwt
from dotenv import load_dotenv

load_dotenv()

# 从环境变量获取 JWT Secret
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not JWT_SECRET:
    print("Error: SUPABASE_JWT_SECRET not found in .env", file=sys.stderr)
    sys.exit(1)

# 创建 JWT payload
now = datetime.now(timezone.utc)
payload = {
    "sub": "test-user-dashboard-123",  # user_id
    "email": "test-dashboard@example.com",
    "role": "authenticated",
    "aud": "authenticated",
    "iss": os.getenv("SUPABASE_ISSUER", "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1"),
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(hours=24)).timestamp()),
}

# 生成 token
token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
print(token)

