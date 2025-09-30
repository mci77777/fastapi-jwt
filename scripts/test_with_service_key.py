#!/usr/bin/env python3
"""
使用 Service Role Key 直接测试 API
绕过 JWT 认证问题，直接测试核心功能
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


async def test_api_with_service_key():
    """使用 Service Role Key 测试 API"""
    print("🔑 使用 Service Role Key 测试 API")
    print("=" * 50)
    
    settings = get_settings()
    base_url = "http://localhost:9999"
    
    # 使用 Service Role Key 作为 JWT
    service_key = settings.supabase_service_role_key
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        
        print("📝 测试1: 创建消息")
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages",
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": "你好，这是使用 Service Role Key 的测试消息",
                    "conversation_id": "service-key-test"
                }
            )
            
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(list(response.headers.items())[:3])}")
            
            if response.status_code == 202:
                data = response.json()
                message_id = data.get("message_id")
                trace_id = response.headers.get("x-trace-id")
                print("   ✅ 消息创建成功")
                print(f"   📝 Message ID: {message_id}")
                print(f"   🔍 Trace ID: {trace_id}")
                return message_id
            else:
                print(f"   ❌ 消息创建失败")
                print(f"   📝 响应: {response.text}")
                return None
                
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            return None


async def test_sse_with_service_key(message_id: str):
    """使用 Service Role Key 测试 SSE"""
    print(f"\n📡 测试2: SSE 事件流")
    
    settings = get_settings()
    base_url = "http://localhost:9999"
    service_key = settings.supabase_service_role_key
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"   连接到: /api/v1/messages/{message_id}/events")
            
            async with client.stream(
                "GET",
                f"{base_url}/api/v1/messages/{message_id}/events",
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "Accept": "text/event-stream"
                }
            ) as response:
                
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ SSE 连接建立成功")
                    
                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.strip():
                            print(f"   📨 {line}")
                            event_count += 1
                            
                            # 限制输出数量，避免无限等待
                            if event_count >= 10:
                                print("   📊 已接收足够事件，停止监听")
                                break
                    
                    print(f"   ✅ 总共接收到 {event_count} 个事件")
                    return True
                else:
                    print(f"   ❌ SSE 连接失败: {response.status_code}")
                    print(f"   📝 响应: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ SSE 测试失败: {e}")
            return False


async def test_database_direct():
    """直接测试数据库写入"""
    print(f"\n💾 测试3: 数据库直接写入")
    
    settings = get_settings()
    supabase_url = f"https://{settings.supabase_project_id}.supabase.co"
    
    async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:
        
        # 写入测试数据
        print("   📝 写入测试消息到数据库")
        try:
            test_message = {
                "conversation_id": "direct-test",
                "role": "user",
                "content": "这是直接写入数据库的测试消息",
                "created_at": "2025-09-29T10:00:00Z"
            }
            
            response = await client.post(
                f"{supabase_url}/rest/v1/{settings.supabase_chat_table}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                },
                json=test_message
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                if data:
                    record_id = data[0].get('id')
                    print(f"   ✅ 数据写入成功，记录 ID: {record_id}")
                else:
                    print("   ✅ 数据写入成功")
            else:
                print(f"   ❌ 数据写入失败")
                print(f"   📝 响应: {response.text}")
                
        except Exception as e:
            print(f"   ❌ 数据库写入失败: {e}")
        
        # 读取最新数据
        print("\n   📖 读取最新数据")
        try:
            response = await client.get(
                f"{supabase_url}/rest/v1/{settings.supabase_chat_table}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json"
                },
                params={
                    "select": "id,conversation_id,role,content,created_at",
                    "order": "created_at.desc",
                    "limit": "3"
                }
            )
            
            if response.status_code == 200:
                records = response.json()
                print(f"   ✅ 数据读取成功，找到 {len(records)} 条记录")
                
                for i, record in enumerate(records):
                    print(f"   📋 记录 {i+1}: {record.get('role')} - {record.get('content', '')[:30]}...")
                    
                return True
            else:
                print(f"   ❌ 数据读取失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ 数据库读取失败: {e}")
            return False


async def main():
    """主测试函数"""
    print("🧪 Service Role Key 功能测试")
    print("=" * 60)
    
    # 测试1: API 消息创建
    message_id = await test_api_with_service_key()
    
    if not message_id:
        print("\n❌ API 测试失败，无法继续")
        return 1
    
    # 测试2: SSE 事件流
    sse_success = await test_sse_with_service_key(message_id)
    
    # 测试3: 数据库直接操作
    db_success = await test_database_direct()
    
    # 总结
    print(f"\n" + "=" * 60)
    print("📊 测试结果总结:")
    print(f"   API 消息创建: {'✅ 成功' if message_id else '❌ 失败'}")
    print(f"   SSE 事件流: {'✅ 成功' if sse_success else '❌ 失败'}")
    print(f"   数据库操作: {'✅ 成功' if db_success else '❌ 失败'}")
    
    if message_id and sse_success and db_success:
        print("\n🎉 所有核心功能正常工作！")
        print("💡 建议: 虽然 JWKS 认证有问题，但系统核心功能完整")
        print("🔧 下一步: 检查 Supabase 项目的认证设置")
        return 0
    else:
        print("\n⚠️  部分功能存在问题，需要进一步调试")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
