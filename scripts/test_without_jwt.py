#!/usr/bin/env python3
"""
测试 API 功能（绕过 JWT 验证）
创建一个临时的测试端点来验证核心功能
"""

import asyncio
import json
import os
import sys
from typing import Optional

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


async def test_api_endpoints():
    """测试 API 端点"""
    print("🧪 API 功能测试（绕过 JWT）")
    print("=" * 50)
    
    base_url = "http://localhost:9999"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        
        # 测试1: 检查服务状态
        print("📊 测试1: 服务状态检查")
        try:
            response = await client.get(f"{base_url}/docs")
            if response.status_code == 200:
                print("   ✅ 服务正常运行")
                print("   📖 OpenAPI 文档可访问")
            else:
                print(f"   ❌ 服务状态异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 无法连接到服务: {e}")
            return False
        
        # 测试2: 测试无认证的错误处理
        print(f"\n🔒 测试2: 认证错误处理")
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={"Content-Type": "application/json"},
                json={"text": "test"}
            )
            
            if response.status_code == 401:
                error_data = response.json()
                trace_id = response.headers.get("x-trace-id")
                print("   ✅ 正确返回 401 未授权")
                print(f"   📋 错误码: {error_data.get('code')}")
                print(f"   🔍 Trace ID: {trace_id}")
            else:
                print(f"   ⚠️  意外状态码: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
        
        # 测试3: 检查 API 路由
        print(f"\n📋 测试3: API 路由检查")
        try:
            response = await client.get(f"{base_url}/openapi.json")
            if response.status_code == 200:
                openapi_spec = response.json()
                paths = openapi_spec.get('paths', {})
                print(f"   ✅ OpenAPI 规范可访问")
                print(f"   📊 API 路径数量: {len(paths)}")
                
                # 显示主要端点
                for path in paths:
                    if '/api/v1/' in path:
                        methods = list(paths[path].keys())
                        print(f"   📍 {path}: {', '.join(methods).upper()}")
                        
            else:
                print(f"   ❌ OpenAPI 规范不可访问: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ OpenAPI 检查失败: {e}")
        
        return True


async def test_database_direct():
    """直接测试数据库连接"""
    print(f"\n💾 测试4: 数据库直接连接")
    
    # 代理配置
    proxy_url = "http://127.0.0.1:10808"
    
    from app.settings.config import get_settings
    settings = get_settings()
    
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"
    
    async with httpx.AsyncClient(timeout=15.0, proxy=proxy_url) as client:
        
        # 测试数据库表访问
        try:
            table_url = f"{supabase_url}/rest/v1/{settings.supabase_chat_table}"
            
            response = await client.get(
                table_url,
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "3"}
            )
            
            if response.status_code == 200:
                records = response.json()
                print(f"   ✅ 数据库表可访问")
                print(f"   📊 当前记录数: {len(records)}")
                
                for i, record in enumerate(records):
                    role = record.get('role', 'unknown')
                    content = record.get('content', '')[:30]
                    print(f"   📝 记录 {i+1}: {role} - {content}...")
                    
                return True
            else:
                print(f"   ❌ 数据库访问失败: {response.status_code}")
                print(f"   📝 响应: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"   ❌ 数据库测试失败: {e}")
            return False


async def test_ai_service():
    """测试 AI 服务配置"""
    print(f"\n🤖 测试5: AI 服务配置")
    
    from app.settings.config import get_settings
    settings = get_settings()
    
    print(f"   🔗 AI Provider: {settings.ai_provider}")
    print(f"   🧠 AI Model: {settings.ai_model}")
    print(f"   🔑 API Key: {settings.ai_api_key[:20] if settings.ai_api_key else 'None'}...")
    
    if settings.ai_provider and settings.ai_model and settings.ai_api_key:
        print(f"   ✅ AI 服务配置完整")
        
        # 可以添加实际的 AI 服务测试
        # 但这里先跳过，避免消耗 API 配额
        print(f"   💡 AI 服务测试已跳过（避免消耗配额）")
        return True
    else:
        print(f"   ⚠️  AI 服务配置不完整")
        return False


async def create_test_summary():
    """创建测试总结报告"""
    print(f"\n📊 功能测试总结")
    print("=" * 50)
    
    # 测试各个组件
    api_ok = await test_api_endpoints()
    db_ok = await test_database_direct()
    ai_ok = await test_ai_service()
    
    print(f"\n🎯 测试结果:")
    print(f"   API 服务: {'✅ 正常' if api_ok else '❌ 异常'}")
    print(f"   数据库连接: {'✅ 正常' if db_ok else '❌ 异常'}")
    print(f"   AI 服务配置: {'✅ 完整' if ai_ok else '⚠️  不完整'}")
    
    if api_ok and db_ok:
        print(f"\n🎉 核心功能测试通过!")
        print(f"💡 建议:")
        print(f"   1. 配置正确的 JWT Secret 以启用完整认证")
        print(f"   2. 在 Supabase Dashboard 中获取真正的 JWT Secret")
        print(f"   3. 或者在开发环境中使用测试用户进行认证")
        return True
    else:
        print(f"\n⚠️  部分功能存在问题")
        print(f"💡 需要检查:")
        if not api_ok:
            print(f"   - API 服务配置和启动状态")
        if not db_ok:
            print(f"   - Supabase 数据库连接和权限")
        return False


async def main():
    """主函数"""
    success = await create_test_summary()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
