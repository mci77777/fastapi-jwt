"""测试 AI 请求记录功能。"""
import asyncio
import sys
from pathlib import Path

# 设置 UTF-8 编码输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE_URL = "http://localhost:9999/api/v1"


async def test_ai_request_recording():
    """测试 AI 请求记录功能。"""
    print("=" * 60)
    print("测试 AI 请求记录功能")
    print("=" * 60)

    # 1. 生成测试 token
    print("\n1. 生成测试 token...")
    import subprocess

    result = subprocess.run(
        ["python", "scripts/create_test_jwt.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip()
    print(f"   ✅ Token: {token[:50]}...")

    # 2. 发起 AI 请求
    print("\n2. 发起 AI 请求...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "text": "测试 AI 请求记录功能",
                "conversation_id": "test-ai-recording-001",
            },
        )

        if response.status_code == 202:
            data = response.json()
            message_id = data.get("message_id")
            print(f"   ✅ AI 请求已创建")
            print(f"   📝 Message ID: {message_id}")
        else:
            print(f"   ❌ AI 请求失败: {response.status_code} - {response.text}")
            return False

    # 3. 等待 AI 请求完成
    print("\n3. 等待 AI 请求完成（3 秒）...")
    await asyncio.sleep(3)

    # 4. 查询数据库验证记录
    print("\n4. 查询数据库验证记录...")
    import subprocess

    result = subprocess.run(
        [
            "sqlite3",
            "db.sqlite3",
            "SELECT user_id, model, count, success_count, error_count, total_latency_ms FROM ai_request_stats ORDER BY created_at DESC LIMIT 5;",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        output = result.stdout.strip()
        if output:
            print("   ✅ 数据库记录：")
            print(f"   {output}")
            return True
        else:
            print("   ⚠️  数据库中暂无记录（可能 AI 请求尚未完成）")
            return False
    else:
        print(f"   ❌ 查询失败: {result.stderr}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ai_request_recording())
    sys.exit(0 if success else 1)

