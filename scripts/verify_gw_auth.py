#!/usr/bin/env python3
"""GW-Auth 网关改造验证脚本。"""
import asyncio
import sys
from typing import Dict, List

import httpx


class GWAuthVerifier:
    """GW-Auth验证器。"""

    def __init__(self, base_url: str = "http://localhost:9999"):
        self.base_url = base_url
        self.results: List[Dict] = []

    def add_result(self, test_name: str, passed: bool, details: Dict = None):
        """添加测试结果。"""
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details or {}
        })
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    async def test_health_endpoints(self) -> bool:
        """测试健康探针端点。"""
        print("\n🔍 测试健康探针端点...")
        
        endpoints = [
            "/api/v1/healthz",
            "/api/v1/livez",
            "/api/v1/readyz"
        ]
        
        all_passed = True
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(f"{self.base_url}{endpoint}")
                    passed = response.status_code == 200
                    all_passed = all_passed and passed
                    
                    self.add_result(
                        f"健康探针 {endpoint}",
                        passed,
                        {
                            "status_code": response.status_code,
                            "response": response.json() if passed else response.text[:100]
                        }
                    )
                except Exception as e:
                    all_passed = False
                    self.add_result(
                        f"健康探针 {endpoint}",
                        False,
                        {"error": str(e)}
                    )
        
        return all_passed

    async def test_metrics_endpoint(self) -> bool:
        """测试Prometheus指标端点。"""
        print("\n🔍 测试Prometheus指标端点...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/metrics")
                
                if response.status_code != 200:
                    self.add_result(
                        "Prometheus指标端点",
                        False,
                        {"status_code": response.status_code}
                    )
                    return False
                
                # 检查是否包含预期的指标
                content = response.text
                expected_metrics = [
                    "auth_requests_total",
                    "jwt_validation_errors_total",
                    "jwks_cache_hits_total",
                    "rate_limit_blocks_total"
                ]
                
                found_metrics = []
                for metric in expected_metrics:
                    if metric in content:
                        found_metrics.append(metric)
                
                passed = len(found_metrics) >= 2  # 至少找到2个指标
                self.add_result(
                    "Prometheus指标端点",
                    passed,
                    {
                        "status_code": response.status_code,
                        "found_metrics": found_metrics,
                        "content_length": len(content)
                    }
                )
                return passed
                
        except Exception as e:
            self.add_result(
                "Prometheus指标端点",
                False,
                {"error": str(e)}
            )
            return False

    async def test_whitelist_no_rate_limit(self) -> bool:
        """测试白名单路径不触发限流。"""
        print("\n🔍 测试白名单路径免限流...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 快速连续请求健康探针（超过QPS限制）
                responses = []
                for _ in range(20):
                    response = await client.get(f"{self.base_url}/api/v1/healthz")
                    responses.append(response.status_code)
                
                # 检查是否有429错误
                has_429 = 429 in responses
                passed = not has_429  # 不应该有429错误
                
                self.add_result(
                    "白名单路径免限流",
                    passed,
                    {
                        "total_requests": len(responses),
                        "status_codes": set(responses),
                        "has_rate_limit": has_429
                    }
                )
                return passed
                
        except Exception as e:
            self.add_result(
                "白名单路径免限流",
                False,
                {"error": str(e)}
            )
            return False

    async def test_config_snapshot(self) -> bool:
        """测试配置快照文件存在。"""
        print("\n🔍 测试配置快照...")
        
        import os
        
        files_to_check = [
            "docs/runbooks/GW_AUTH_ROLLBACK.md",
            ".env.example",
            "app/settings/config.py"
        ]
        
        all_exist = True
        for file_path in files_to_check:
            exists = os.path.exists(file_path)
            all_exist = all_exist and exists
            
            self.add_result(
                f"配置文件 {file_path}",
                exists,
                {"exists": exists}
            )
        
        return all_exist

    def print_summary(self):
        """打印测试摘要。"""
        print("\n" + "=" * 60)
        print("📊 测试摘要")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        
        print(f"总测试数: {total}")
        print(f"通过: {passed} ✅")
        print(f"失败: {failed} ❌")
        print(f"通过率: {passed/total*100:.1f}%")
        
        if failed > 0:
            print("\n❌ 失败的测试:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}")
                    if result["details"]:
                        for key, value in result["details"].items():
                            print(f"    {key}: {value}")
        
        print("=" * 60)
        
        return failed == 0

    async def run_all_tests(self) -> bool:
        """运行所有测试。"""
        print("🚀 开始验证 GW-Auth 网关改造...")
        
        # 测试1: 健康探针
        await self.test_health_endpoints()
        
        # 测试2: Prometheus指标
        await self.test_metrics_endpoint()
        
        # 测试3: 白名单免限流
        await self.test_whitelist_no_rate_limit()
        
        # 测试4: 配置快照
        self.test_config_snapshot()
        
        # 打印摘要
        return self.print_summary()


async def main():
    """主函数。"""
    verifier = GWAuthVerifier()
    success = await verifier.run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！GW-Auth 网关改造验证成功")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败，请检查上述错误")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

