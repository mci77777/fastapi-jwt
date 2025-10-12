"""测试 Dashboard WebSocket 连接。

用法:
    python scripts/test_websocket_connection.py
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from websockets.exceptions import WebSocketException


async def test_websocket_connection():
    """测试 WebSocket 连接。"""
    # 从 localStorage 获取的 token（需要手动替换）
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3J5a2dsaXZyd3pjeWtoaG54d296LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJ0ZXN0LXVzZXItYWRtaW4iLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzYwMjQzMTQzLCJpYXQiOjE3NjAyMzk1NDMsImVtYWlsIjoiYWRtaW5AdGVzdC5sb2NhbCIsInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiaXNfYW5vbnltb3VzIjpmYWxzZSwidXNlcl9tZXRhZGF0YSI6eyJ1c2VybmFtZSI6ImFkbWluIiwiaXNfYWRtaW4iOnRydWV9LCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJ0ZXN0IiwicHJvdmlkZXJzIjpbInRlc3QiXX19.IvEXc6EJS1GzT40eBZLknLoU2kDsUWasP_nk4v5JMLo"

    url = f"ws://localhost:9999/api/v1/ws/dashboard?token={token}"

    print(f"[*] Connecting to: {url}")
    print()

    try:
        async with websockets.connect(url) as websocket:
            print("[+] WebSocket connection successful!")
            print()

            # 接收前 3 条消息
            for i in range(3):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=15)
                    data = json.loads(message)
                    print(f"[MSG {i+1}]:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    print()
                except asyncio.TimeoutError:
                    print(f"[!] Message timeout (15 seconds)")
                    break

    except WebSocketException as e:
        print(f"[-] WebSocket error: {e}")
        print()
        print("Possible reasons:")
        print("1. Backend server not running")
        print("2. JWT token expired")
        print("3. Backend WebSocket endpoint error")

    except Exception as e:
        print(f"[-] Unknown error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("Dashboard WebSocket 连接测试")
    print("=" * 60)
    print()
    
    asyncio.run(test_websocket_connection())

