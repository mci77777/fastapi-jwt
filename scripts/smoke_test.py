#!/usr/bin/env python3
"""
GymBro API 完整冒烟测试
包括用户注册、JWT获取、API测试和数据验证
"""

import asyncio
import json
import os
import random
import string
import sys
import time
from typing import Optional

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


class SmokeTest:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "http://localhost:9999"
        self.supabase_url = f"https://{self.settings.supabase_project_id}.supabase.co"
        self.test_email = self._generate_test_email()
        self.test_password = "TestPassword123!"
        self.access_token: Optional[str] = None
        self.message_id: Optional[str] = None

    def _generate_test_email(self) -> str:
        """生成随机测试邮箱"""
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"test_{random_suffix}@example.com"

    async def step_1_register_user(self) -> bool:
        """步骤1: 在Supabase中注册测试用户"""
        print("🔐 步骤1: 注册测试用户")
        print(f"   邮箱: {self.test_email}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.supabase_url}/auth/v1/signup",
                    headers={
                        "apikey": self.settings.supabase_service_role_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": self.test_email,
                        "password": self.test_password
                    }
                )

                if response.status_code in [200, 400]:  # 400可能是用户已存在
                    print("   ✅ 用户注册成功（或已存在）")
                    return True
                else:
                    print(f"   ❌ 注册失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 注册请求失败: {e}")
                return False

    async def step_2_get_jwt_token(self) -> bool:
        """步骤2: 获取JWT访问令牌"""
        print("🎫 步骤2: 获取JWT访问令牌")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.supabase_url}/auth/v1/token?grant_type=password",
                    headers={
                        "apikey": self.settings.supabase_service_role_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": self.test_email,
                        "password": self.test_password
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    if self.access_token:
                        print(f"   ✅ JWT令牌获取成功 (长度: {len(self.access_token)})")
                        return True
                    else:
                        print("   ❌ 响应中未找到access_token")
                        return False
                else:
                    print(f"   ❌ 获取令牌失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 令牌请求失败: {e}")
                return False

    async def step_3_test_api_auth(self) -> bool:
        """步骤3: 测试API认证"""
        print("🔒 步骤3: 测试API认证")

        async with httpx.AsyncClient() as client:
            # 测试有效JWT
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": "你好，帮我用一句话总结 Supabase JWT 验证流程",
                        "conversation_id": "smoke-test-001"
                    }
                )

                if response.status_code == 202:
                    data = response.json()
                    self.message_id = data.get("message_id")
                    trace_id = response.headers.get("x-trace-id")
                    print(f"   ✅ 认证成功，消息已创建")
                    print(f"   📝 Message ID: {self.message_id}")
                    print(f"   🔍 Trace ID: {trace_id}")
                    return True
                else:
                    print(f"   ❌ API调用失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ API请求失败: {e}")
                return False

    async def step_4_test_invalid_jwt(self) -> bool:
        """步骤4: 测试无效JWT（负例测试）"""
        print("🚫 步骤4: 测试无效JWT")

        # 伪造JWT
        bad_token = self.access_token[:-1] + "x" if self.access_token else "invalid"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/messages",
                    headers={
                        "Authorization": f"Bearer {bad_token}",
                        "Content-Type": "application/json"
                    },
                    json={"text": "test"}
                )

                if response.status_code == 401:
                    error_data = response.json()
                    trace_id = response.headers.get("x-trace-id")
                    print("   ✅ 正确拒绝无效JWT")
                    print(f"   📋 错误码: {error_data.get('code')}")
                    print(f"   🔍 Trace ID: {trace_id}")
                    return True
                else:
                    print(f"   ❌ 应该返回401，实际返回: {response.status_code}")
                    return False

            except Exception as e:
                print(f"   ❌ 请求失败: {e}")
                return False

    async def step_5_test_sse_stream(self) -> bool:
        """步骤5: 测试SSE事件流"""
        print("📡 步骤5: 测试SSE事件流")

        if not self.message_id:
            print("   ❌ 没有message_id，跳过SSE测试")
            return False

        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "GET",
                    f"{self.base_url}/api/v1/messages/{self.message_id}/events",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "text/event-stream"
                    },
                    timeout=10.0
                ) as response:

                    if response.status_code == 200:
                        print("   ✅ SSE连接建立成功")

                        event_count = 0
                        async for line in response.aiter_lines():
                            if line.startswith("event:") or line.startswith("data:"):
                                print(f"   📨 {line}")
                                event_count += 1

                            if event_count >= 5:  # 限制输出数量
                                break

                        print(f"   ✅ 接收到 {event_count} 个事件")
                        return True
                    else:
                        print(f"   ❌ SSE连接失败: {response.status_code}")
                        return False

            except Exception as e:
                print(f"   ❌ SSE测试失败: {e}")
                return False

    async def step_6_verify_database(self) -> bool:
        """步骤6: 验证数据库持久化"""
        print("💾 步骤6: 验证数据库持久化")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/{self.settings.supabase_chat_table}",
                    headers={
                        "apikey": self.settings.supabase_service_role_key,
                        "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "select": "id,role,content,created_at",
                        "order": "created_at.desc",
                        "limit": "5"
                    }
                )

                if response.status_code == 200:
                    records = response.json()
                    print(f"   ✅ 数据库连接成功，找到 {len(records)} 条记录")

                    for record in records[:2]:  # 显示最新2条
                        print(f"   📝 {record.get('role')}: {record.get('content', '')[:50]}...")

                    return True
                else:
                    print(f"   ❌ 数据库查询失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 数据库验证失败: {e}")
                return False

    async def run_all_tests(self) -> bool:
        """运行所有测试步骤"""
        print("🚀 开始GymBro API完整冒烟测试")
        print("=" * 60)

        tests = [
            self.step_1_register_user,
            self.step_2_get_jwt_token,
            self.step_3_test_api_auth,
            self.step_4_test_invalid_jwt,
            self.step_5_test_sse_stream,
            self.step_6_verify_database
        ]

        results = []
        for i, test in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}]", end=" ")
            result = await test()
            results.append(result)

            if not result:
                print(f"   ⚠️  测试失败，但继续执行后续测试...")

            time.sleep(1)  # 短暂延迟

        print("\n" + "=" * 60)
        print("📊 测试结果总结:")

        passed = sum(results)
        total = len(results)

        test_names = [
            "用户注册", "JWT获取", "API认证", "无效JWT拒绝",
            "SSE事件流", "数据库持久化"
        ]

        for i, (name, result) in enumerate(zip(test_names, results)):
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   {i+1}. {name}: {status}")

        print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

        if passed == total:
            print("🎉 所有测试通过！系统运行正常！")
            return True
        else:
            print("⚠️  部分测试失败，请检查配置和服务状态")
            return False


async def main():
    """主函数"""
    smoke_test = SmokeTest()
    success = await smoke_test.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
