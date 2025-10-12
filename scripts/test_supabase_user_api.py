"""测试 Supabase User API 响应。"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


async def test_user_api():
    """测试 Supabase User API。"""
    if not SUPABASE_PROJECT_ID or not SUPABASE_SERVICE_ROLE_KEY:
        print("Error: SUPABASE_PROJECT_ID or SUPABASE_SERVICE_ROLE_KEY not set")
        return

    base_url = f"https://{SUPABASE_PROJECT_ID}.supabase.co"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    # 测试不存在的用户
    test_uid = "test-user-dashboard-123"
    url = f"{base_url}/auth/v1/admin/users/{test_uid}"

    print(f"Testing Supabase User API: {url}")
    print(f"User ID: {test_uid}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            print(f"\nStatus Code: {response.status_code}")
            print(f"Response: {response.text}")

            if response.status_code == 200:
                data = response.json()
                user = data.get("user", data)
                print(f"\nUser ID from response: {user.get('id')}")
                print(f"User email: {user.get('email')}")
        except Exception as exc:
            print(f"\nError: {exc}")


if __name__ == "__main__":
    asyncio.run(test_user_api())

