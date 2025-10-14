#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控管线测试脚本：验证 Dashboard 监控指标。

功能：
1. AI 请求连通性测试
2. Token API 连通性测试
3. JWT 连通性测试
4. 后端服务健康检查

使用方法：
    python scripts/test_monitoring_pipeline.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from dotenv import load_dotenv

load_dotenv()

# 配置
BASE_URL = "http://localhost:9999/api/v1"


def print_section(title: str) -> None:
    """打印分节标题。"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def get_test_token() -> str:
    """获取测试 JWT token。"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/access_token",
                json={"username": "admin", "password": "123456"},
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and "access_token" in data["data"]:
                return data["data"]["access_token"]
            elif "access_token" in data:
                return data["access_token"]
            else:
                raise ValueError(f"Unexpected response format: {data}")

    except Exception as e:
        print(f"❌ Token 获取失败: {e}")
        sys.exit(1)


def test_backend_health() -> bool:
    """测试后端服务健康状态。"""
    print_section("1. 后端服务健康检查")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{BASE_URL}/healthz")
            response.raise_for_status()
            data = response.json()

            print(f"✅ 后端服务健康")
            print(f"   状态: {data.get('status', 'unknown')}")
            print(f"   时间: {data.get('timestamp', 'unknown')}")
            return True

    except Exception as e:
        print(f"❌ 后端服务不健康: {e}")
        return False


def test_token_api_connectivity() -> bool:
    """测试 Token API 连通性。"""
    print_section("2. Token API 连通性测试")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/access_token",
                json={"username": "admin", "password": "123456"},
            )
            response.raise_for_status()
            data = response.json()

            print(f"✅ Token API 连通正常")
            print(f"   响应码: {response.status_code}")
            print(f"   Token 长度: {len(data.get('data', {}).get('access_token', ''))}")
            return True

    except Exception as e:
        print(f"❌ Token API 连通失败: {e}")
        return False


def test_jwt_connectivity(token: str) -> bool:
    """测试 JWT 连通性（验证成功率）。"""
    print_section("3. JWT 连通性测试")

    try:
        with httpx.Client(timeout=10.0) as client:
            # 测试受保护的端点
            response = client.get(
                f"{BASE_URL}/stats/dashboard",
                headers={"Authorization": f"Bearer {token}"},
                params={"time_window": "24h"},
            )
            response.raise_for_status()
            data = response.json()

            print(f"✅ JWT 验证成功")
            print(f"   响应码: {response.status_code}")

            # 获取 JWT 可用性指标
            if "data" in data and "jwt_availability" in data["data"]:
                jwt_stats = data["data"]["jwt_availability"]
                print(f"\n📊 JWT 连通性指标:")
                print(f"   成功率: {jwt_stats.get('success_rate', 0)}%")
                print(f"   总请求数: {jwt_stats.get('total_requests', 0)}")
                print(f"   成功请求数: {jwt_stats.get('successful_requests', 0)}")

            return True

    except Exception as e:
        print(f"❌ JWT 连通性测试失败: {e}")
        return False


def test_ai_request_connectivity(token: str) -> bool:
    """测试 AI 请求连通性。"""
    print_section("4. AI 请求连通性测试")

    try:
        with httpx.Client(timeout=10.0) as client:
            # 获取 AI 模型列表
            response = client.get(
                f"{BASE_URL}/llm/models",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            print(f"✅ AI 请求连通正常")
            print(f"   响应码: {response.status_code}")

            # 显示模型列表
            if "data" in data and "items" in data["data"]:
                models = data["data"]["items"]
                print(f"   可用模型数: {len(models)}")
                if models:
                    print(f"\n📋 模型列表:")
                    for model in models[:3]:  # 只显示前 3 个
                        print(f"   - {model.get('model_name', 'unknown')}")
                        print(f"     提供商: {model.get('provider', 'unknown')}")
                        print(f"     状态: {'✅ 活跃' if model.get('is_active') else '❌ 未激活'}")

            return True

    except Exception as e:
        print(f"❌ AI 请求连通性测试失败: {e}")
        return False


def test_api_connectivity(token: str) -> bool:
    """测试 API 连通性状态。"""
    print_section("5. API 连通性状态")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL}/stats/api-connectivity",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            print(f"✅ API 连通性查询成功")

            # 显示连通性指标
            if "data" in data:
                api_stats = data["data"]
            else:
                api_stats = data

            print(f"\n📊 API 连通性指标:")
            print(f"   监控运行中: {'✅ 是' if api_stats.get('is_running') else '❌ 否'}")
            print(f"   健康端点数: {api_stats.get('healthy_endpoints', 0)}")
            print(f"   总端点数: {api_stats.get('total_endpoints', 0)}")
            print(f"   连通率: {api_stats.get('connectivity_rate', 0)}%")
            print(f"   最后检查: {api_stats.get('last_check', 'unknown')}")

            return True

    except Exception as e:
        print(f"❌ API 连通性查询失败: {e}")
        return False


def test_dashboard_stats(token: str) -> bool:
    """测试 Dashboard 统计数据。"""
    print_section("6. Dashboard 统计数据")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL}/stats/dashboard",
                headers={"Authorization": f"Bearer {token}"},
                params={"time_window": "24h"},
            )
            response.raise_for_status()
            data = response.json()

            print(f"✅ Dashboard 数据获取成功")

            # 显示统计数据
            if "data" in data:
                stats = data["data"]
            else:
                stats = data

            print(f"\n📊 Dashboard 统计数据:")
            print(f"   日活用户数: {stats.get('daily_active_users', 0)}")

            ai_requests = stats.get("ai_requests", {})
            print(f"   AI 请求总数: {ai_requests.get('total', 0)}")
            print(f"   AI 请求成功: {ai_requests.get('success', 0)}")
            print(f"   AI 请求错误: {ai_requests.get('error', 0)}")
            print(f"   平均延迟: {ai_requests.get('avg_latency_ms', 0)} ms")

            api_conn = stats.get("api_connectivity", {})
            print(f"   API 连通率: {api_conn.get('connectivity_rate', 0)}%")

            jwt_avail = stats.get("jwt_availability", {})
            print(f"   JWT 成功率: {jwt_avail.get('success_rate', 0)}%")

            return True

    except Exception as e:
        print(f"❌ Dashboard 数据获取失败: {e}")
        return False


def main():
    print("=" * 80)
    print("  监控管线测试脚本")
    print("=" * 80)
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  后端: {BASE_URL}")

    # 测试后端健康
    if not test_backend_health():
        print("\n❌ 后端服务不可用，终止测试")
        return 1

    # 测试 Token API
    if not test_token_api_connectivity():
        print("\n❌ Token API 不可用，终止测试")
        return 1

    # 获取 token
    print_section("获取测试 Token")
    token = get_test_token()
    print(f"✅ Token 获取成功: {token[:50]}...")

    # 运行所有测试
    results = {
        "JWT 连通性": test_jwt_connectivity(token),
        "AI 请求连通性": test_ai_request_connectivity(token),
        "API 连通性状态": test_api_connectivity(token),
        "Dashboard 统计数据": test_dashboard_stats(token),
    }

    # 总结
    print_section("测试总结")
    passed = sum(results.values())
    total = len(results)

    print(f"测试结果: {passed}/{total} 通过\n")
    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}  {name}")

    if passed == total:
        print(f"\n🎉 所有监控管线测试通过！")
        return 0
    else:
        print(f"\n⚠️  部分测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())

