#!/usr/bin/env python3
"""Dashboard 功能验证脚本 - 测试健康检查、指标获取、前端集成"""
import asyncio
import httpx
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.settings.config import get_settings

settings = get_settings()
BASE_URL = "http://localhost:9999"


async def test_health_endpoints():
    """测试健康检查端点"""
    print("\n" + "=" * 60)
    print("测试健康检查端点")
    print("=" * 60)
    
    endpoints = [
        ("/api/v1/healthz", "健康检查"),
        ("/api/v1/livez", "存活探针"),
        ("/api/v1/readyz", "就绪探针"),
    ]
    
    async with httpx.AsyncClient(timeout=10) as client:
        for path, name in endpoints:
            url = f"{BASE_URL}{path}"
            try:
                response = await client.get(url)
                print(f"\n{name}: {url}")
                print(f"  状态码: {response.status_code}")
                print(f"  响应: {response.json()}")
                
                if response.status_code == 200:
                    print(f"  ✓ {name}正常")
                else:
                    print(f"  ✗ {name}异常")
                    return False
            except Exception as e:
                print(f"  ✗ {name}失败: {e}")
                return False
    
    return True


async def test_metrics_endpoint():
    """测试 Prometheus 指标端点"""
    print("\n" + "=" * 60)
    print("测试 Prometheus 指标端点")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/metrics"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            print(f"\nURL: {url}")
            print(f"状态码: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            
            if response.status_code != 200:
                print(f"✗ 指标端点返回错误状态码")
                return False
            
            metrics_text = response.text
            print(f"\n指标数据长度: {len(metrics_text)} 字节")
            
            # 验证关键指标存在
            required_metrics = [
                "auth_requests_total",
                "jwt_validation_errors_total",
                "active_connections",
                "rate_limit_blocks_total",
            ]
            
            missing_metrics = []
            for metric in required_metrics:
                if metric in metrics_text:
                    print(f"  ✓ {metric} 存在")
                else:
                    print(f"  ✗ {metric} 缺失")
                    missing_metrics.append(metric)
            
            if missing_metrics:
                print(f"\n✗ 缺失指标: {', '.join(missing_metrics)}")
                return False
            
            print("\n✓ 所有关键指标存在")
            return True
            
        except Exception as e:
            print(f"✗ 指标端点测试失败: {e}")
            return False


async def test_supabase_status():
    """测试 Supabase 状态端点"""
    print("\n" + "=" * 60)
    print("测试 Supabase 状态端点")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/llm/status/supabase"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            print(f"\nURL: {url}")
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"响应: {data}")
                print(f"  状态: {data.get('status')}")
                print(f"  延迟: {data.get('latency_ms')}ms")
                print("  ✓ Supabase 状态端点正常")
                return True
            else:
                print(f"  ✗ Supabase 状态端点异常")
                return False
                
        except Exception as e:
            print(f"  ✗ Supabase 状态测试失败: {e}")
            return False


async def test_monitor_status():
    """测试监控状态端点"""
    print("\n" + "=" * 60)
    print("测试监控状态端点")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/llm/monitor/status"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            print(f"\nURL: {url}")
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"响应: {data}")
                print(f"  运行中: {data.get('is_running')}")
                print(f"  间隔: {data.get('interval_seconds')}秒")
                print("  ✓ 监控状态端点正常")
                return True
            else:
                print(f"  ✗ 监控状态端点异常")
                return False
                
        except Exception as e:
            print(f"  ✗ 监控状态测试失败: {e}")
            return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("Dashboard 功能验证")
    print("=" * 60)
    print(f"后端地址: {BASE_URL}")
    
    results = []
    
    # 测试健康检查端点
    results.append(("健康检查", await test_health_endpoints()))
    
    # 测试指标端点
    results.append(("Prometheus 指标", await test_metrics_endpoint()))
    
    # 测试 Supabase 状态
    results.append(("Supabase 状态", await test_supabase_status()))
    
    # 测试监控状态
    results.append(("监控状态", await test_monitor_status()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ 所有测试通过！Dashboard 功能正常")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查后端服务")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

