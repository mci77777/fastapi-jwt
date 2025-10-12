"""生成测试 JWT token。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

import httpx

BASE_URL = "http://localhost:9999/api/v1"


async def generate_token():
    """生成测试 token。"""
    async with httpx.AsyncClient() as client:
        # 调用 dialog 端点生成 token
        response = await client.post(
            f"{BASE_URL}/llm/tests/dialog",
            json={
                "prompt_id": 1,
                "endpoint_id": 1,
                "message": "test message for dashboard",
                "username": "test-user-dashboard",
            },
        )

        if response.status_code == 200:
            data = response.json()
            # 从响应中提取 token
            token = data.get("jwt_token") or data.get("data", {}).get("jwt_token")
            if token:
                print(token)
                return token
        else:
            print(f"Error: {response.status_code} - {response.text}", file=sys.stderr)
            return None


if __name__ == "__main__":
    token = asyncio.run(generate_token())
    sys.exit(0 if token else 1)

