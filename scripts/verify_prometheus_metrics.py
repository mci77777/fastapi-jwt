"""验证 Prometheus 指标更新逻辑。

测试步骤：
1. 启动后端服务
2. 登录获取 token
3. 使用 token 访问受保护端点
4. 检查 Prometheus 指标是否更新
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx


BASE_URL = "http://localhost:9999/api/v1"


async def verify_prometheus_metrics():
    """验证 Prometheus 指标更新。"""
    print("=" * 60)
    print("Verify Prometheus Metrics Update")
    print("=" * 60)

    # 1. 登录获取 token
    print("\n1. Login to get token...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/base/access_token",
            json={"username": "admin", "password": "123456"},
        )

        if response.status_code != 200:
            print(f"   [FAIL] Login failed: {response.status_code} - {response.text}")
            return False

        data = response.json()
        if data.get("code") != 200:
            print(f"   [FAIL] Login failed: {data}")
            return False

        token = data["data"]["access_token"]
        print(f"   [OK] Token: {token[:50]}...")

    # 2. 使用 token 访问受保护端点
    print("\n2. Access protected endpoint with token...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/stats/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code != 200:
            print(f"   [FAIL] Access failed: {response.status_code} - {response.text}")
            return False

        print(f"   [OK] Access success: {response.status_code}")

    # 3. 检查 Prometheus 指标
    print("\n3. Check Prometheus metrics...")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9999/api/v1/metrics")

        if response.status_code != 200:
            print(f"   [FAIL] Get metrics failed: {response.status_code}")
            return False

        metrics_text = response.text

        # 检查 auth_requests_total 指标
        if "auth_requests_total" not in metrics_text:
            print("   [FAIL] auth_requests_total metric not found")
            return False

        # 提取 auth_requests_total 指标值
        success_count = 0
        failure_count = 0

        for line in metrics_text.split("\n"):
            if line.startswith("auth_requests_total"):
                if 'status="success"' in line:
                    success_count = float(line.split()[-1])
                elif 'status="failure"' in line:
                    failure_count = float(line.split()[-1])

        print(f'   [OK] auth_requests_total{{status="success"}} = {success_count}')
        print(f'   [OK] auth_requests_total{{status="failure"}} = {failure_count}')

        if success_count == 0:
            print("   [WARN] Success count is 0 (may be first run)")
            return False

        print(f"\n   [OK] Prometheus metrics updated successfully!")
        return True


if __name__ == "__main__":
    success = asyncio.run(verify_prometheus_metrics())
    sys.exit(0 if success else 1)

