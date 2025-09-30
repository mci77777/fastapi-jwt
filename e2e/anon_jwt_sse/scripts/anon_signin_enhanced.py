"""
增强版匿名用户登录脚本
支持两种匿名JWT获取方式：
1. Edge Function方式 (推荐) - 基于docs/匿名用户获取JWT.md规范
2. Supabase原生匿名登录 (需要Dashboard启用)

运行：python e2e/anon_jwt_sse/scripts/anon_signin_enhanced.py [--method edge|native]
"""
import asyncio
import argparse
import json
import os
import pathlib
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import aiohttp
import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class EnhancedAnonAuth:
    """增强版匿名认证客户端"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.api_base = os.getenv("API_BASE", "http://localhost:9999")
        
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")
        
        self.artifacts_dir = pathlib.Path(__file__).parent.parent / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_token_via_edge_function(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        通过Edge Function获取匿名JWT token
        这是推荐的方式，基于docs/匿名用户获取JWT.md规范
        """
        if not trace_id:
            trace_id = f"edge-anon-{uuid.uuid4().hex[:8]}"
        
        edge_url = f"{self.supabase_url}/functions/v1/get-anon-token"
        headers = {
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id,
            "User-Agent": "E2E-Enhanced-Client/1.0"
        }
        
        print(f"🔑 通过Edge Function获取匿名JWT...")
        print(f"📍 URL: {edge_url}")
        print(f"🔍 Trace ID: {trace_id}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    edge_url,
                    headers=headers,
                    json={},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        print(f"✅ Edge Function获取成功")
                        print(f"🆔 用户ID: {data['user']['id']}")
                        print(f"📧 邮箱: {data['user']['email']}")
                        print(f"⏰ 过期时间: {data['expires_at']}")
                        
                        # 保存token
                        await self._save_token_data(data, "edge_function", trace_id)
                        return data
                        
                    elif response.status == 429:
                        error_data = json.loads(response_text)
                        raise Exception(f"Rate limit exceeded: {error_data}")
                    else:
                        raise Exception(f"Edge Function failed: {response.status} - {response_text}")
                        
            except Exception as e:
                print(f"❌ Edge Function方式失败: {e}")
                raise
    
    async def get_token_via_native_auth(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        通过Supabase原生匿名登录获取JWT token
        需要在Supabase Dashboard中启用匿名登录
        """
        if not self.anon_key:
            raise ValueError("SUPABASE_ANON_KEY is required for native auth")
        
        if not trace_id:
            trace_id = f"native-anon-{uuid.uuid4().hex[:8]}"
        
        auth_url = f"{self.supabase_url}/auth/v1/signup"
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id
        }
        
        print(f"🔑 通过原生匿名登录获取JWT...")
        print(f"📍 URL: {auth_url}")
        print(f"🔍 Trace ID: {trace_id}")
        
        # 尝试匿名登录
        payload = {"options": {"anonymous": True}}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    auth_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        print(f"✅ 原生匿名登录成功")
                        
                        # 转换为统一格式
                        unified_data = {
                            "access_token": data["access_token"],
                            "token_type": data.get("token_type", "bearer"),
                            "expires_in": data.get("expires_in", 3600),
                            "expires_at": data.get("expires_at"),
                            "user": data.get("user", {}),
                            "session": data.get("session", {})
                        }
                        
                        # 保存token
                        await self._save_token_data(unified_data, "native_auth", trace_id)
                        return unified_data
                        
                    elif response.status == 422:
                        error_data = json.loads(response_text)
                        if "anonymous_provider_disabled" in response_text:
                            raise Exception("Anonymous sign-ins are disabled in Supabase Dashboard")
                        else:
                            raise Exception(f"Native auth failed: {error_data}")
                    else:
                        raise Exception(f"Native auth failed: {response.status} - {response_text}")
                        
            except Exception as e:
                print(f"❌ 原生认证方式失败: {e}")
                raise
    
    async def _save_token_data(self, token_data: Dict[str, Any], method: str, trace_id: str):
        """保存token数据到artifacts目录"""
        
        # 保存完整数据
        full_file = self.artifacts_dir / f"anon_token_{method}.json"
        with open(full_file, 'w', encoding='utf-8') as f:
            json.dump({
                "method": method,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "token_data": token_data
            }, f, indent=2, ensure_ascii=False)
        
        # 保存兼容格式（与现有E2E测试兼容）
        compat_file = self.artifacts_dir / "token.json"
        compat_data = {
            "access_token": token_data["access_token"],
            "token_type": token_data.get("token_type", "bearer"),
            "expires_in": token_data.get("expires_in", 3600)
        }
        
        # 添加用户信息（如果存在）
        if "user" in token_data:
            compat_data["user"] = token_data["user"]
        
        with open(compat_file, 'w', encoding='utf-8') as f:
            json.dump(compat_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Token数据已保存: {full_file}")
        print(f"💾 兼容格式已保存: {compat_file}")
    
    async def verify_token_with_api(self, token: str) -> Dict[str, Any]:
        """验证token是否能正常访问API"""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Trace-Id": f"verify-{uuid.uuid4().hex[:8]}"
        }
        
        # 测试多个端点
        test_endpoints = [
            f"{self.api_base}/api/v1/me",
            f"{self.api_base}/api/v1/messages",
            f"{self.api_base}/health"
        ]
        
        results = {}
        
        for endpoint in test_endpoints:
            print(f"🔍 测试端点: {endpoint}")
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        endpoint,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        result = {
                            "status_code": response.status,
                            "headers": dict(response.headers),
                            "response": await response.text(),
                            "success": response.status < 500
                        }
                        
                        results[endpoint] = result
                        
                        if response.status == 200:
                            print(f"  ✅ 成功 (200)")
                        elif response.status in [401, 403]:
                            print(f"  🔐 认证/权限问题 ({response.status})")
                        elif response.status == 429:
                            print(f"  ⏱️ 限流 (429)")
                        else:
                            print(f"  ❌ 失败 ({response.status})")
                            
                except Exception as e:
                    results[endpoint] = {
                        "error": str(e),
                        "success": False
                    }
                    print(f"  ❌ 异常: {e}")
        
        # 保存验证结果
        verify_file = self.artifacts_dir / "token_verification_enhanced.json"
        with open(verify_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "api_base": self.api_base,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 验证结果已保存: {verify_file}")
        return results

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="增强版匿名用户JWT获取")
    parser.add_argument(
        "--method", 
        choices=["edge", "native", "both"], 
        default="edge",
        help="获取方式: edge(Edge Function), native(原生), both(两种都试)"
    )
    parser.add_argument(
        "--verify", 
        action="store_true",
        help="验证获取的token是否能访问API"
    )
    
    args = parser.parse_args()
    
    print("🚀 增强版匿名用户JWT获取测试开始...")
    print(f"📋 方式: {args.method}")
    print("=" * 60)
    
    try:
        client = EnhancedAnonAuth()
        token_data = None
        
        if args.method in ["edge", "both"]:
            try:
                print("\n🔄 尝试Edge Function方式...")
                token_data = await client.get_token_via_edge_function()
                print("✅ Edge Function方式成功")
            except Exception as e:
                print(f"❌ Edge Function方式失败: {e}")
                if args.method == "edge":
                    return 1
        
        if args.method in ["native", "both"] and not token_data:
            try:
                print("\n🔄 尝试原生认证方式...")
                token_data = await client.get_token_via_native_auth()
                print("✅ 原生认证方式成功")
            except Exception as e:
                print(f"❌ 原生认证方式失败: {e}")
                if args.method == "native":
                    return 1
        
        if not token_data:
            print("❌ 所有方式都失败了")
            return 1
        
        # 验证token
        if args.verify:
            print("\n" + "=" * 60)
            print("🔍 验证token...")
            await client.verify_token_with_api(token_data["access_token"])
        
        print("\n" + "=" * 60)
        print("✅ 增强版匿名用户JWT获取测试完成")
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
