#!/usr/bin/env python3
"""
简单的 API 测试脚本
测试 JWT 认证和 API 端点
"""

import asyncio
import json
import httpx


async def test_api():
    """测试 API 端点"""
    base_url = "http://localhost:9999"
    
    async with httpx.AsyncClient() as client:
        print("测试 1: 无效 JWT - 应返回 401")
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer invalid-token"
                },
                json={"text": "hello"}
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.text}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                print("✅ 测试通过 - 正确返回 401")
            else:
                print("❌ 测试失败 - 应该返回 401")
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
        
        print("\n" + "="*50 + "\n")
        
        print("测试 2: 缺少 Authorization 头 - 应返回 401")
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={"Content-Type": "application/json"},
                json={"text": "hello"}
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.text}")
            
            if response.status_code == 401:
                print("✅ 测试通过 - 正确返回 401")
            else:
                print("❌ 测试失败 - 应该返回 401")
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
        
        print("\n" + "="*50 + "\n")
        
        print("测试 3: 检查服务健康状态")
        try:
            response = await client.get(f"{base_url}/docs")
            print(f"文档页面状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ 服务正常运行")
            else:
                print("❌ 服务可能有问题")
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_api())
