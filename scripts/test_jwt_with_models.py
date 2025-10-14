#!/usr/bin/env python3
"""
JWT 测试脚本 - 使用真实 email 和模型管理 API

测试流程：
1. 使用真实 email 地址注册/登录（调用 /api/v1/base/access_token）
2. 获取 JWT token
3. 使用 token 调用模型列表 API（GET /api/v1/llm/models）
4. 使用 token 调用模型映射 API（GET /api/v1/llm/model-groups）
5. 验证返回数据是否正确
"""

import asyncio
import os
import sys
from typing import Optional

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


class JWTModelTest:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "http://localhost:9999/api/v1"
        self.supabase_url = f"https://{self.settings.supabase_project_id}.supabase.co"
        
        # 从环境变量读取测试用户信息
        self.test_email = os.getenv("TEST_USER_EMAIL", "test@example.com")
        self.test_password = os.getenv("TEST_USER_PASSWORD", "TestPassword123!")
        
        self.access_token: Optional[str] = None

    async def step_1_register_user(self) -> bool:
        """步骤 1: 在 Supabase 中注册测试用户"""
        print("🔐 步骤 1: 注册测试用户")
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

                if response.status_code in [200, 400]:  # 400 可能是用户已存在
                    print("   ✅ 用户注册成功（或已存在）")
                    return True
                else:
                    print(f"   ❌ 注册失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 注册请求失败: {e}")
                return False

    async def step_2_get_jwt_token(self) -> bool:
        """步骤 2: 获取 JWT 访问令牌"""
        print("🎫 步骤 2: 获取 JWT 访问令牌")

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
                        print(f"   ✅ JWT 令牌获取成功 (长度: {len(self.access_token)})")
                        return True
                    else:
                        print("   ❌ 响应中未找到 access_token")
                        return False
                else:
                    print(f"   ❌ 获取令牌失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 获取令牌请求失败: {e}")
                return False

    async def step_3_test_models_api(self) -> bool:
        """步骤 3: 测试模型列表 API"""
        print("📋 步骤 3: 测试模型列表 API")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/llm/models",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "page": 1,
                        "page_size": 10
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    total = data.get("total", 0)
                    print(f"   ✅ 模型列表获取成功，共 {total} 个模型")
                    
                    # 显示前 3 个模型
                    for i, model in enumerate(models[:3], 1):
                        print(f"   📦 模型 {i}: {model.get('name')} ({model.get('model')})")
                    
                    return True
                else:
                    print(f"   ❌ 模型列表获取失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 模型列表请求失败: {e}")
                return False

    async def step_4_test_mappings_api(self) -> bool:
        """步骤 4: 测试模型映射 API"""
        print("🗺️ 步骤 4: 测试模型映射 API")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/llm/model-groups",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    mappings = data.get("data", [])
                    print(f"   ✅ 模型映射获取成功，共 {len(mappings)} 条映射")
                    
                    # 显示前 3 条映射
                    for i, mapping in enumerate(mappings[:3], 1):
                        print(f"   🔗 映射 {i}: {mapping.get('name')} → {mapping.get('default_model')}")
                    
                    return True
                else:
                    print(f"   ❌ 模型映射获取失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 模型映射请求失败: {e}")
                return False

    async def step_5_test_diagnose_api(self) -> bool:
        """步骤 5: 测试模型诊断 API"""
        print("🔍 步骤 5: 测试模型诊断 API")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/llm/models/check-all",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("data", [])
                    
                    available_count = sum(1 for r in results if r.get("status") == "available")
                    unavailable_count = sum(1 for r in results if r.get("status") == "unavailable")
                    
                    print(f"   ✅ 模型诊断完成：{available_count} 个可用，{unavailable_count} 个不可用")
                    return True
                else:
                    print(f"   ❌ 模型诊断失败: {response.status_code} - {response.text}")
                    return False

            except Exception as e:
                print(f"   ❌ 模型诊断请求失败: {e}")
                return False

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("JWT 模型管理测试")
        print("=" * 60)
        print()

        # 步骤 1: 注册用户
        if not await self.step_1_register_user():
            print("\n❌ 测试失败：用户注册失败")
            return False

        # 步骤 2: 获取 JWT Token
        if not await self.step_2_get_jwt_token():
            print("\n❌ 测试失败：JWT Token 获取失败")
            return False

        # 步骤 3: 测试模型列表 API
        if not await self.step_3_test_models_api():
            print("\n❌ 测试失败：模型列表 API 调用失败")
            return False

        # 步骤 4: 测试模型映射 API
        if not await self.step_4_test_mappings_api():
            print("\n❌ 测试失败：模型映射 API 调用失败")
            return False

        # 步骤 5: 测试模型诊断 API
        if not await self.step_5_test_diagnose_api():
            print("\n❌ 测试失败：模型诊断 API 调用失败")
            return False

        print()
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True


async def main():
    """主函数"""
    test = JWTModelTest()
    success = await test.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

