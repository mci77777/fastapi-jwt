#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前端调试辅助脚本
用于自动化常见的前端调试任务
"""

import httpx
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# 设置 Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


class FrontendDebugger:
    """前端调试工具类"""

    def __init__(self, frontend_url: str = "http://localhost:3101", backend_url: str = "http://localhost:9999"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.client = httpx.Client(timeout=10.0)

    def check_services(self) -> Dict[str, Any]:
        """检查前后端服务状态"""
        print("\n" + "=" * 60)
        print("检查服务状态")
        print("=" * 60)

        results = {
            "frontend": {"url": self.frontend_url, "status": "unknown"},
            "backend": {"url": self.backend_url, "status": "unknown"},
            "backend_health": {"url": f"{self.backend_url}/api/v1/healthz", "status": "unknown"},
        }

        # 检查前端
        try:
            response = self.client.get(self.frontend_url)
            results["frontend"]["status"] = "running" if response.status_code == 200 else f"error ({response.status_code})"
            results["frontend"]["status_code"] = response.status_code
            print(f"✅ 前端服务: {self.frontend_url} - {response.status_code}")
        except Exception as e:
            results["frontend"]["status"] = "offline"
            results["frontend"]["error"] = str(e)
            print(f"❌ 前端服务: {self.frontend_url} - 离线")
            print(f"   错误: {e}")

        # 检查后端
        try:
            response = self.client.get(f"{self.backend_url}/docs")
            results["backend"]["status"] = "running" if response.status_code == 200 else f"error ({response.status_code})"
            results["backend"]["status_code"] = response.status_code
            print(f"✅ 后端服务: {self.backend_url} - {response.status_code}")
        except Exception as e:
            results["backend"]["status"] = "offline"
            results["backend"]["error"] = str(e)
            print(f"❌ 后端服务: {self.backend_url} - 离线")
            print(f"   错误: {e}")

        # 检查后端健康检查
        try:
            response = self.client.get(f"{self.backend_url}/api/v1/healthz")
            health_data = response.json()
            results["backend_health"]["status"] = "healthy" if response.status_code == 200 else "unhealthy"
            results["backend_health"]["data"] = health_data
            print(f"✅ 后端健康检查: {health_data}")
        except Exception as e:
            results["backend_health"]["status"] = "error"
            results["backend_health"]["error"] = str(e)
            print(f"❌ 后端健康检查失败: {e}")

        return results

    def test_api_endpoints(self, token: str = None) -> List[Dict[str, Any]]:
        """测试常用 API 端点"""
        print("\n" + "=" * 60)
        print("测试 API 端点")
        print("=" * 60)

        endpoints = [
            {"method": "GET", "path": "/api/v1/healthz", "auth": False},
            {"method": "GET", "path": "/api/v1/stats/dashboard", "auth": True},
            {"method": "GET", "path": "/api/v1/stats/daily-active-users", "auth": True},
            {"method": "GET", "path": "/api/v1/llm/models", "auth": False},
        ]

        results = []
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        for endpoint in endpoints:
            url = f"{self.backend_url}{endpoint['path']}"
            method = endpoint["method"]
            requires_auth = endpoint["auth"]

            # 跳过需要认证但没有 token 的端点
            if requires_auth and not token:
                print(f"⏭️  {method} {endpoint['path']} - 跳过（需要 token）")
                results.append(
                    {
                        "method": method,
                        "path": endpoint["path"],
                        "status": "skipped",
                        "reason": "no token provided",
                    }
                )
                continue

            try:
                if method == "GET":
                    response = self.client.get(url, headers=headers if requires_auth else {})
                else:
                    response = self.client.request(method, url, headers=headers if requires_auth else {})

                result = {
                    "method": method,
                    "path": endpoint["path"],
                    "status_code": response.status_code,
                    "status": "success" if 200 <= response.status_code < 300 else "error",
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                }

                try:
                    result["data"] = response.json()
                except:
                    result["data"] = response.text[:200]

                results.append(result)

                status_icon = "✅" if result["status"] == "success" else "❌"
                print(f"{status_icon} {method} {endpoint['path']} - {response.status_code} ({result['response_time_ms']:.2f}ms)")

            except Exception as e:
                result = {
                    "method": method,
                    "path": endpoint["path"],
                    "status": "error",
                    "error": str(e),
                }
                results.append(result)
                print(f"❌ {method} {endpoint['path']} - 错误: {e}")

        return results

    def check_network_performance(self) -> Dict[str, Any]:
        """检查网络性能"""
        print("\n" + "=" * 60)
        print("检查网络性能")
        print("=" * 60)

        test_urls = [
            f"{self.frontend_url}/",
            f"{self.backend_url}/api/v1/healthz",
            f"{self.backend_url}/docs",
        ]

        results = []
        for url in test_urls:
            try:
                start_time = datetime.now()
                response = self.client.get(url)
                end_time = datetime.now()
                elapsed_ms = (end_time - start_time).total_seconds() * 1000

                result = {
                    "url": url,
                    "status_code": response.status_code,
                    "response_time_ms": elapsed_ms,
                    "content_length": len(response.content),
                }
                results.append(result)

                print(f"✅ {url}")
                print(f"   状态码: {response.status_code}")
                print(f"   响应时间: {elapsed_ms:.2f}ms")
                print(f"   内容大小: {len(response.content)} bytes")

            except Exception as e:
                result = {"url": url, "status": "error", "error": str(e)}
                results.append(result)
                print(f"❌ {url} - 错误: {e}")

        return {"tests": results, "timestamp": datetime.now().isoformat()}

    def generate_test_token(self) -> str:
        """生成测试 JWT token"""
        print("\n" + "=" * 60)
        print("生成测试 JWT token")
        print("=" * 60)

        try:
            import subprocess

            result = subprocess.run(
                ["python", "scripts/create_test_jwt.py"],
                capture_output=True,
                text=True,
                check=True,
            )
            token = result.stdout.strip()
            print(f"✅ Token 生成成功")
            print(f"   Token: {token[:50]}...")
            return token
        except Exception as e:
            print(f"❌ Token 生成失败: {e}")
            return None

    def run_full_diagnostic(self, token: str = None):
        """运行完整诊断"""
        print("\n" + "=" * 60)
        print("前端调试诊断报告")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. 检查服务状态
        service_status = self.check_services()

        # 2. 检查网络性能
        network_perf = self.check_network_performance()

        # 3. 测试 API 端点
        if not token:
            print("\n⚠️  未提供 token，尝试生成测试 token...")
            token = self.generate_test_token()

        api_results = self.test_api_endpoints(token)

        # 4. 生成总结
        print("\n" + "=" * 60)
        print("诊断总结")
        print("=" * 60)

        # 服务状态总结
        frontend_ok = service_status["frontend"]["status"] == "running"
        backend_ok = service_status["backend"]["status"] == "running"
        health_ok = service_status["backend_health"]["status"] == "healthy"

        print(f"前端服务: {'✅ 正常' if frontend_ok else '❌ 异常'}")
        print(f"后端服务: {'✅ 正常' if backend_ok else '❌ 异常'}")
        print(f"健康检查: {'✅ 正常' if health_ok else '❌ 异常'}")

        # API 测试总结
        api_success = sum(1 for r in api_results if r.get("status") == "success")
        api_total = len([r for r in api_results if r.get("status") != "skipped"])
        print(f"API 测试: {api_success}/{api_total} 通过")

        # 性能总结
        avg_response_time = sum(r.get("response_time_ms", 0) for r in network_perf["tests"]) / len(network_perf["tests"])
        print(f"平均响应时间: {avg_response_time:.2f}ms")

        # 保存报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "service_status": service_status,
            "network_performance": network_perf,
            "api_tests": api_results,
            "summary": {
                "frontend_ok": frontend_ok,
                "backend_ok": backend_ok,
                "health_ok": health_ok,
                "api_success_rate": f"{api_success}/{api_total}",
                "avg_response_time_ms": avg_response_time,
            },
        }

        report_file = f"debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 完整报告已保存到: {report_file}")

        return report


def main():
    """主函数"""
    debugger = FrontendDebugger()

    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "check":
            debugger.check_services()
        elif command == "test":
            token = sys.argv[2] if len(sys.argv) > 2 else None
            debugger.test_api_endpoints(token)
        elif command == "perf":
            debugger.check_network_performance()
        elif command == "token":
            debugger.generate_test_token()
        else:
            print(f"未知命令: {command}")
            print("可用命令: check, test, perf, token, full")
    else:
        # 默认运行完整诊断
        debugger.run_full_diagnostic()


if __name__ == "__main__":
    main()

