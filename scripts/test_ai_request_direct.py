"""直接测试 AI 请求并查看响应。"""
import asyncio
import io
import subprocess
import sys

# 修复 Windows 控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx


async def test_ai_request():
    """测试 AI 请求。"""
    # 1. 生成 token
    result = subprocess.run(
        ["python", "scripts/create_test_jwt.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip()
    print(f"Token: {token[:50]}...")

    # 2. 发起 AI 请求
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9999/api/v1/messages",
            json={"text": "测试 AI 请求", "conversation_id": "test-001"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 202:
            data = response.json()
            message_id = data.get("message_id")
            print(f"\nMessage ID: {message_id}")

            # 3. 等待 AI 请求完成
            print("\n等待 AI 请求完成（10 秒）...")
            await asyncio.sleep(10)

            # 4. 查询数据库
            result = subprocess.run(
                [
                    "sqlite3",
                    "db.sqlite3",
                    "SELECT user_id, model, count, success_count, error_count FROM ai_request_stats ORDER BY created_at DESC LIMIT 1;",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"\nDatabase Record: {result.stdout.strip()}")


if __name__ == "__main__":
    asyncio.run(test_ai_request())

