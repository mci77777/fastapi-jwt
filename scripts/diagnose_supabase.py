#!/usr/bin/env python3
"""
Supabase 连接诊断脚本
详细检查 Supabase 配置和连接状态
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


async def diagnose_supabase():
    """诊断 Supabase 配置"""
    print("🔍 Supabase 连接诊断")
    print("=" * 50)

    settings = get_settings()

    # 显示配置信息
    print("📋 当前配置:")
    print(f"   Project ID: {settings.supabase_project_id}")
    print(f"   JWKS URL: {settings.supabase_jwks_url}")
    print(f"   Issuer: {settings.supabase_issuer}")
    print(f"   Audience: {settings.supabase_audience}")
    print(f"   Service Key: {settings.supabase_service_role_key[:20]}...")
    print(f"   Chat Table: {settings.supabase_chat_table}")

    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"

    async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:

        # 测试1: 基础连通性
        print(f"\n🌐 测试1: 基础连通性")
        print(f"   目标: {supabase_url}")

        try:
            response = await client.get(supabase_url)
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(list(response.headers.items())[:3])}")

            if response.status_code == 200:
                print("   ✅ 基础连接正常")
            else:
                print(f"   ⚠️  响应异常: {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ 连接失败: {e}")
            return False

        # 测试2: JWKS 端点详细检查
        print(f"\n🔑 测试2: JWKS 端点详细检查")
        jwks_url = str(settings.supabase_jwks_url)
        print(f"   URL: {jwks_url}")

        try:
            response = await client.get(jwks_url)
            print(f"   状态码: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type')}")

            if response.status_code == 200:
                try:
                    jwks_data = response.json()
                    keys_count = len(jwks_data.get('keys', []))
                    print(f"   ✅ JWKS 可访问，包含 {keys_count} 个密钥")

                    # 显示第一个密钥的信息
                    if keys_count > 0:
                        first_key = jwks_data['keys'][0]
                        print(f"   🔐 第一个密钥: kty={first_key.get('kty')}, use={first_key.get('use')}")

                except json.JSONDecodeError:
                    print(f"   ⚠️  响应不是有效的 JSON: {response.text[:100]}")

            elif response.status_code == 404:
                print("   ❌ JWKS 端点不存在 (404)")
                print("   💡 可能原因:")
                print("      - Project ID 错误")
                print("      - Supabase 项目未启用认证")
                print("      - URL 格式不正确")

            else:
                print(f"   ❌ JWKS 访问失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ JWKS 请求失败: {e}")

        # 测试3: 认证端点检查
        print(f"\n🔐 测试3: 认证端点检查")
        auth_url = f"{supabase_url}/auth/v1"
        print(f"   URL: {auth_url}")

        try:
            response = await client.get(auth_url)
            print(f"   状态码: {response.status_code}")

            if response.status_code in [200, 404, 405]:  # 405 Method Not Allowed 也是正常的
                print("   ✅ 认证服务可访问")
            else:
                print(f"   ⚠️  认证服务响应异常: {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ 认证端点请求失败: {e}")

        # 测试4: REST API 端点检查
        print(f"\n📊 测试4: REST API 端点检查")
        rest_url = f"{supabase_url}/rest/v1/"
        print(f"   URL: {rest_url}")

        try:
            response = await client.get(
                rest_url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}"
                }
            )
            print(f"   状态码: {response.status_code}")

            if response.status_code == 200:
                print("   ✅ REST API 可访问")

                # 尝试获取 OpenAPI 规范
                try:
                    api_spec = response.json()
                    if 'paths' in api_spec:
                        paths_count = len(api_spec['paths'])
                        print(f"   📋 API 规范包含 {paths_count} 个路径")
                except:
                    print("   📋 REST API 响应格式未知")

            elif response.status_code == 401:
                print("   ❌ Service Role Key 无效或权限不足")
            elif response.status_code == 404:
                print("   ❌ REST API 端点不存在")
            else:
                print(f"   ❌ REST API 访问失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ REST API 请求失败: {e}")

        # 测试5: 特定表检查
        print(f"\n📋 测试5: 数据库表检查")
        table_url = f"{supabase_url}/rest/v1/{settings.supabase_chat_table}"
        print(f"   表名: {settings.supabase_chat_table}")
        print(f"   URL: {table_url}")

        try:
            response = await client.get(
                table_url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "1"}
            )
            print(f"   状态码: {response.status_code}")

            if response.status_code == 200:
                records = response.json()
                print(f"   ✅ 表存在且可访问，当前记录数: {len(records)}")
            elif response.status_code == 404:
                print("   ❌ 表不存在")
                print("   💡 请执行 SQL 脚本创建表: docs/jwt改造/supabase_schema.sql")
            elif response.status_code == 401:
                print("   ❌ 权限不足，无法访问表")
            else:
                print(f"   ❌ 表访问失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ 表检查请求失败: {e}")

    print(f"\n" + "=" * 50)
    print("🎯 诊断建议:")
    print("1. 如果 JWKS 端点返回 404，请检查 Project ID 是否正确")
    print("2. 如果认证失败，请检查 Service Role Key 是否有效")
    print("3. 如果表不存在，请在 Supabase SQL Editor 中执行建表脚本")
    print("4. 确保 Supabase 项目已启用认证功能")

    return True


async def test_manual_jwt():
    """手动测试 JWT 创建（如果可能）"""
    print(f"\n🧪 手动 JWT 测试")
    print("=" * 30)

    settings = get_settings()
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"

    # 使用固定测试用户
    test_email = "test@example.com"
    test_password = "TestPassword123!"

    async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:

        # 尝试注册
        print("👤 尝试注册测试用户...")
        try:
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

            print(f"   注册状态码: {response.status_code}")
            if response.status_code in [200, 400]:
                print("   ✅ 用户注册成功（或已存在）")
            else:
                print(f"   ⚠️  注册响应: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ 注册失败: {e}")

        # 尝试登录获取 JWT
        print("\n🎫 尝试获取 JWT 令牌...")
        try:
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

            print(f"   登录状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                if access_token:
                    print(f"   ✅ JWT 获取成功 (长度: {len(access_token)})")
                    print(f"   🔑 Token 前缀: {access_token[:50]}...")
                    return access_token
                else:
                    print("   ❌ 响应中未找到 access_token")
            else:
                print(f"   ❌ 登录失败: {response.text[:200]}")

        except Exception as e:
            print(f"   ❌ JWT 获取失败: {e}")

    return None


async def main():
    """主函数"""
    await diagnose_supabase()
    jwt_token = await test_manual_jwt()

    if jwt_token:
        print(f"\n🎉 JWT 令牌获取成功！可以进行 API 测试")
        return 0
    else:
        print(f"\n⚠️  JWT 令牌获取失败，请检查 Supabase 配置")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
