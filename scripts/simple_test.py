#!/usr/bin/env python3
"""
简化的API测试脚本
逐步测试各个组件
"""

import asyncio
import json
import os
import sys
from typing import Optional

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings

# 代理配置
PROXY_URL = "http://127.0.0.1:10808"


async def test_local_api():
    """测试本地API基础功能"""
    print("🔧 测试1: 本地API基础功能")

    base_url = "http://localhost:9999"

    async with httpx.AsyncClient() as client:
        # 测试服务健康状态
        try:
            response = await client.get(f"{base_url}/docs")
            if response.status_code == 200:
                print("   ✅ 服务正常运行")
            else:
                print(f"   ❌ 服务状态异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 无法连接到服务: {e}")
            return False

        # 测试无效JWT认证
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={
                    "Authorization": "Bearer invalid-token",
                    "Content-Type": "application/json"
                },
                json={"text": "test"}
            )

            if response.status_code == 401:
                error_data = response.json()
                trace_id = response.headers.get("x-trace-id")
                print("   ✅ JWT认证正常工作")
                print(f"   📋 错误码: {error_data.get('code')}")
                print(f"   🔍 Trace ID: {trace_id}")
                return True
            else:
                print(f"   ❌ JWT认证异常: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ API测试失败: {e}")
            return False


async def test_supabase_connection():
    """测试Supabase连接"""
    print("\n🌐 测试2: Supabase连接")

    settings = get_settings()
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"

    async with httpx.AsyncClient(timeout=10.0, proxy=PROXY_URL) as client:
        # 测试JWKS端点
        try:
            jwks_url = str(settings.supabase_jwks_url)
            print(f"   🔗 测试JWKS: {jwks_url}")

            response = await client.get(jwks_url)
            if response.status_code == 200:
                jwks_data = response.json()
                keys_count = len(jwks_data.get('keys', []))
                print(f"   ✅ JWKS端点可访问，包含 {keys_count} 个密钥")
            else:
                print(f"   ❌ JWKS端点不可访问: {response.status_code}")
                return False

        except Exception as e:
            print(f"   ❌ JWKS测试失败: {e}")
            return False

        # 测试Supabase REST API
        try:
            api_url = f"{supabase_url}/rest/v1/"
            print(f"   🔗 测试REST API: {api_url}")

            response = await client.get(
                api_url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}"
                }
            )

            if response.status_code == 200:
                print("   ✅ Supabase REST API可访问")
                return True
            else:
                print(f"   ❌ Supabase REST API不可访问: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"   ❌ Supabase API测试失败: {e}")
            return False


async def test_database_table():
    """测试数据库表"""
    print("\n💾 测试3: 数据库表")

    settings = get_settings()
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"

    async with httpx.AsyncClient(timeout=10.0, proxy=PROXY_URL) as client:
        try:
            table_url = f"{supabase_url}/rest/v1/{settings.supabase_chat_table}"
            print(f"   🔗 测试表: {settings.supabase_chat_table}")

            response = await client.get(
                table_url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "1"}
            )

            if response.status_code == 200:
                records = response.json()
                print(f"   ✅ 表 '{settings.supabase_chat_table}' 存在且可访问")
                print(f"   📊 当前记录数: {len(records)}")
                return True
            else:
                print(f"   ❌ 表不存在或不可访问: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")

                if response.status_code == 404:
                    print("   💡 提示: 请运行 SQL 脚本创建数据库表")
                    print("   📄 脚本位置: docs/jwt改造/supabase_schema.sql")

                return False

        except Exception as e:
            print(f"   ❌ 数据库表测试失败: {e}")
            return False


async def test_jwt_creation():
    """测试JWT创建（使用测试用户）"""
    print("\n🎫 测试4: JWT令牌创建")

    settings = get_settings()
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"

    # 使用一个固定的测试邮箱
    test_email = "test@example.com"
    test_password = "TestPassword123!"

    async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:
        # 先尝试注册用户
        try:
            print(f"   📧 尝试注册用户: {test_email}")

            response = await client.post(
                f"{supabase_url}/auth/v1/signup",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Content-Type": "application/json"
                },
                json={
                    "email": test_email,
                    "password": test_password
                }
            )

            if response.status_code in [200, 400]:  # 400可能是用户已存在
                print("   ✅ 用户注册成功（或已存在）")
            else:
                print(f"   ⚠️  注册响应: {response.status_code} - {response.text[:100]}")

        except Exception as e:
            print(f"   ⚠️  注册失败: {e}")

        # 尝试获取JWT令牌
        try:
            print("   🔑 尝试获取JWT令牌")

            response = await client.post(
                f"{supabase_url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Content-Type": "application/json"
                },
                json={
                    "email": test_email,
                    "password": test_password
                }
            )

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                if access_token:
                    print(f"   ✅ JWT令牌获取成功 (长度: {len(access_token)})")
                    return access_token
                else:
                    print("   ❌ 响应中未找到access_token")
                    return None
            else:
                print(f"   ❌ 获取令牌失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"   ❌ JWT获取失败: {e}")
            return None


async def test_api_with_jwt(jwt_token: str):
    """使用真实JWT测试API"""
    print("\n🚀 测试5: 使用真实JWT测试API")

    base_url = "http://localhost:9999"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": "你好，这是一个测试消息",
                    "conversation_id": "test-conversation"
                }
            )

            if response.status_code == 202:
                data = response.json()
                message_id = data.get("message_id")
                trace_id = response.headers.get("x-trace-id")
                print("   ✅ API调用成功")
                print(f"   📝 Message ID: {message_id}")
                print(f"   🔍 Trace ID: {trace_id}")
                return message_id
            else:
                print(f"   ❌ API调用失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"   ❌ API测试失败: {e}")
            return None


async def main():
    """主测试函数"""
    print("🧪 GymBro API 逐步测试")
    print("=" * 50)

    # 测试1: 本地API
    if not await test_local_api():
        print("\n❌ 本地API测试失败，请检查服务是否正常启动")
        return 1

    # 测试2: Supabase连接
    if not await test_supabase_connection():
        print("\n❌ Supabase连接测试失败，请检查网络和配置")
        return 1

    # 测试3: 数据库表
    if not await test_database_table():
        print("\n⚠️  数据库表测试失败，但继续其他测试")

    # 测试4: JWT创建
    jwt_token = await test_jwt_creation()
    if not jwt_token:
        print("\n❌ JWT创建失败，无法进行完整API测试")
        return 1

    # 测试5: 完整API测试
    message_id = await test_api_with_jwt(jwt_token)
    if message_id:
        print("\n🎉 所有核心功能测试通过！")
        return 0
    else:
        print("\n⚠️  API测试部分失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
