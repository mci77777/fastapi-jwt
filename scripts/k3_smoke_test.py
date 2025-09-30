#!/usr/bin/env python3
"""K3 限流与反滥用功能冒烟测试。"""

import asyncio
import json
import logging
import time
from typing import Dict, List

import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class K3SmokeTest:
    """K3功能冒烟测试。"""
    
    def __init__(self, base_url: str = "http://localhost:9999"):
        self.base_url = base_url
        self.test_results: List[Dict] = []
    
    async def run_all_tests(self):
        """运行所有测试。"""
        logger.info("开始K3限流与反滥用功能冒烟测试")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 测试1: 基础限流功能
            await self.test_rate_limiting(client)
            
            # 测试2: 匿名用户限流
            await self.test_anonymous_rate_limiting(client)
            
            # 测试3: 可疑UA限流
            await self.test_suspicious_user_agent(client)
            
            # 测试4: SSE并发控制（模拟）
            await self.test_sse_concurrency_simulation(client)
            
            # 测试5: 冷静期机制
            await self.test_cooldown_mechanism(client)
        
        # 输出测试结果
        self.print_test_results()
    
    async def test_rate_limiting(self, client: httpx.AsyncClient):
        """测试基础限流功能。"""
        logger.info("测试1: 基础限流功能")
        
        # 快速发送多个请求触发限流
        requests_sent = 0
        rate_limited = False
        
        for i in range(25):  # 超过默认QPS限制
            try:
                response = await client.get(f"{self.base_url}/api/v1/messages/test/events")
                requests_sent += 1
                
                if response.status_code == 429:
                    rate_limited = True
                    retry_after = response.headers.get("Retry-After")
                    
                    logger.info(
                        "限流触发 status_code=%d retry_after=%s response=%s",
                        response.status_code, retry_after, response.text[:200]
                    )
                    break
                    
            except Exception as e:
                logger.warning("请求失败: %s", e)
        
        self.test_results.append({
            "test": "rate_limiting",
            "requests_sent": requests_sent,
            "rate_limited": rate_limited,
            "status": "PASS" if rate_limited else "FAIL"
        })
    
    async def test_anonymous_rate_limiting(self, client: httpx.AsyncClient):
        """测试匿名用户限流。"""
        logger.info("测试2: 匿名用户限流")
        
        # 不带认证头的请求
        requests_sent = 0
        rate_limited = False
        
        for i in range(10):  # 匿名用户限制更严格
            try:
                response = await client.get(f"{self.base_url}/api/v1/messages/test/events")
                requests_sent += 1
                
                if response.status_code == 429:
                    rate_limited = True
                    logger.info("匿名用户限流触发 response=%s", response.text[:200])
                    break
                    
            except Exception as e:
                logger.warning("匿名请求失败: %s", e)
        
        self.test_results.append({
            "test": "anonymous_rate_limiting",
            "requests_sent": requests_sent,
            "rate_limited": rate_limited,
            "status": "PASS" if rate_limited else "FAIL"
        })
    
    async def test_suspicious_user_agent(self, client: httpx.AsyncClient):
        """测试可疑User-Agent限流。"""
        logger.info("测试3: 可疑User-Agent限流")
        
        suspicious_uas = [
            "curl/7.68.0",
            "python-requests/2.28.0",
            "PostmanRuntime/7.29.0",
            "bot-crawler/1.0",
            "test-agent"
        ]
        
        results = []
        
        for ua in suspicious_uas:
            requests_sent = 0
            rate_limited = False
            
            for i in range(8):  # 可疑UA限制更严格
                try:
                    response = await client.get(
                        f"{self.base_url}/api/v1/messages/test/events",
                        headers={"User-Agent": ua}
                    )
                    requests_sent += 1
                    
                    if response.status_code == 429:
                        rate_limited = True
                        logger.info("可疑UA限流触发 ua=%s response=%s", ua, response.text[:200])
                        break
                        
                except Exception as e:
                    logger.warning("可疑UA请求失败 ua=%s error=%s", ua, e)
            
            results.append({
                "user_agent": ua,
                "requests_sent": requests_sent,
                "rate_limited": rate_limited
            })
        
        self.test_results.append({
            "test": "suspicious_user_agent",
            "results": results,
            "status": "PASS" if any(r["rate_limited"] for r in results) else "FAIL"
        })
    
    async def test_sse_concurrency_simulation(self, client: httpx.AsyncClient):
        """测试SSE并发控制（模拟）。"""
        logger.info("测试4: SSE并发控制模拟")
        
        # 由于没有真实的JWT认证，这里只能模拟测试SSE端点的响应
        try:
            response = await client.get(f"{self.base_url}/api/v1/messages/test/events")
            
            # 检查是否返回了认证错误（预期行为）
            auth_required = response.status_code in [401, 403]
            
            logger.info(
                "SSE端点响应 status_code=%d auth_required=%s",
                response.status_code, auth_required
            )
            
            self.test_results.append({
                "test": "sse_concurrency_simulation",
                "status_code": response.status_code,
                "auth_required": auth_required,
                "status": "PASS" if auth_required else "INFO"
            })
            
        except Exception as e:
            logger.warning("SSE并发测试失败: %s", e)
            self.test_results.append({
                "test": "sse_concurrency_simulation",
                "error": str(e),
                "status": "FAIL"
            })
    
    async def test_cooldown_mechanism(self, client: httpx.AsyncClient):
        """测试冷静期机制。"""
        logger.info("测试5: 冷静期机制")
        
        # 发送大量失败请求触发冷静期
        failure_count = 0
        cooldown_triggered = False
        
        for i in range(15):  # 超过失败阈值
            try:
                # 发送到不存在的端点触发404
                response = await client.get(f"{self.base_url}/api/v1/nonexistent")
                
                if response.status_code >= 400:
                    failure_count += 1
                
                # 检查是否触发了冷静期（429错误）
                if response.status_code == 429 and "cooldown" in response.text.lower():
                    cooldown_triggered = True
                    logger.info("冷静期触发 response=%s", response.text[:200])
                    break
                    
            except Exception as e:
                logger.warning("冷静期测试请求失败: %s", e)
        
        self.test_results.append({
            "test": "cooldown_mechanism",
            "failure_count": failure_count,
            "cooldown_triggered": cooldown_triggered,
            "status": "PASS" if cooldown_triggered else "INFO"
        })
    
    def print_test_results(self):
        """打印测试结果。"""
        logger.info("=" * 60)
        logger.info("K3 冒烟测试结果汇总")
        logger.info("=" * 60)
        
        for result in self.test_results:
            test_name = result["test"]
            status = result["status"]
            
            logger.info(f"测试: {test_name}")
            logger.info(f"状态: {status}")
            
            # 输出详细信息
            for key, value in result.items():
                if key not in ["test", "status"]:
                    logger.info(f"  {key}: {value}")
            
            logger.info("-" * 40)
        
        # 统计
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "PASS")
        
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"通过率: {passed_tests/total_tests*100:.1f}%")


async def main():
    """主函数。"""
    tester = K3SmokeTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
