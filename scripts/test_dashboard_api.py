"""测试 Dashboard API 端点。"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import load_dotenv

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

BASE_URL = "http://localhost:9999/api/v1"


def create_test_token():
    """创建测试 JWT token。"""
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        raise ValueError("SUPABASE_JWT_SECRET not found in .env")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "test-user-dashboard-123",
        "email": "test-dashboard@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": os.getenv("SUPABASE_ISSUER", "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1"),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


async def test_all_endpoints():
    """测试所有 Dashboard API 端点。"""
    # 生成测试 token
    token = create_test_token()

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        print("\n" + "=" * 80)
        print("Dashboard API 端点测试")
        print("=" * 80)

        # 测试 1: GET /stats/dashboard
        print("\n[1/8] 测试 GET /stats/dashboard")
        try:
            response = await client.get(f"{BASE_URL}/stats/dashboard?time_window=24h", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 日活用户数: {data.get('daily_active_users')}")
                print(f"  ✓ AI 请求统计: {data.get('ai_requests')}")
                print(f"  ✓ API 连通性: {data.get('api_connectivity')}")
                print(f"  ✓ JWT 可用性: {data.get('jwt_availability')}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 2: GET /stats/daily-active-users
        print("\n[2/8] 测试 GET /stats/daily-active-users")
        try:
            response = await client.get(f"{BASE_URL}/stats/daily-active-users?time_window=24h", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 响应: {data}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 3: GET /stats/ai-requests
        print("\n[3/8] 测试 GET /stats/ai-requests")
        try:
            response = await client.get(f"{BASE_URL}/stats/ai-requests?time_window=24h", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 响应: {data}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 4: GET /stats/api-connectivity
        print("\n[4/8] 测试 GET /stats/api-connectivity")
        try:
            response = await client.get(f"{BASE_URL}/stats/api-connectivity", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 响应: {data}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 5: GET /stats/jwt-availability
        print("\n[5/8] 测试 GET /stats/jwt-availability")
        try:
            response = await client.get(f"{BASE_URL}/stats/jwt-availability", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 响应: {data}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 6: GET /logs/recent
        print("\n[6/8] 测试 GET /logs/recent")
        try:
            response = await client.get(f"{BASE_URL}/logs/recent?level=WARNING&limit=10", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 日志级别: {data.get('level')}")
                print(f"  ✓ 日志数量: {data.get('count')}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 7: GET /stats/config
        print("\n[7/8] 测试 GET /stats/config")
        try:
            response = await client.get(f"{BASE_URL}/stats/config", headers=headers)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 配置: {data.get('config')}")
                print(f"  ✓ 更新时间: {data.get('updated_at')}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        # 测试 8: PUT /stats/config
        print("\n[8/8] 测试 PUT /stats/config")
        try:
            new_config = {
                "websocket_push_interval": 15,
                "http_poll_interval": 45,
                "log_retention_size": 200,
            }
            response = await client.put(f"{BASE_URL}/stats/config", headers=headers, json=new_config)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 更新后配置: {data.get('config')}")
                print(f"  ✓ 更新时间: {data.get('updated_at')}")
            else:
                print(f"  ✗ 失败: {response.text}")
        except Exception as exc:
            print(f"  ✗ 异常: {exc}")

        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_all_endpoints())

