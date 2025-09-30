#!/usr/bin/env python3
"""测试 JWT 认证的 API 端点。"""

import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("❌ 需要安装 httpx: pip install httpx")
    sys.exit(1)


def load_env_file():
    """加载 .env 文件。"""
    env_file = Path(__file__).parent.parent / ".env"
    env_vars = {}
    
    if not env_file.exists():
        print(f"❌ .env 文件不存在: {env_file}")
        return env_vars
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def create_test_jwt(env_vars):
    """创建一个测试用的 JWT token。
    
    注意：这里我们使用 Supabase service role key 来模拟一个有效的 JWT。
    在实际应用中，JWT 应该由 Supabase Auth 服务生成。
    """
    service_role_key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_role_key:
        print("❌ SUPABASE_SERVICE_ROLE_KEY 未配置")
        return None
    
    # 对于测试目的，我们可以使用 service role key
    # 但在生产环境中，应该使用真实的用户 JWT
    return service_role_key


def test_api_endpoint(base_url, endpoint, token, method="GET", data=None):
    """测试 API 端点。"""
    url = f"{base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔍 测试 {method} {endpoint}")
        
        with httpx.Client(timeout=30.0) as client:
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "POST":
                response = client.post(url, headers=headers, json=data)
            else:
                print(f"❌ 不支持的方法: {method}")
                return False
            
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ 请求成功")
            try:
                result = response.json()
                print(f"   📋 响应: {json.dumps(result, indent=2, ensure_ascii=False)[:200]}...")
            except:
                print(f"   📋 响应: {response.text[:200]}...")
            return True
        elif response.status_code == 401:
            print("   ❌ 认证失败 (401)")
            print(f"   📋 错误: {response.text}")
            return False
        else:
            print(f"   ⚠️  意外状态码: {response.status_code}")
            print(f"   📋 响应: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        return False


def test_sse_endpoint(base_url, endpoint, token):
    """测试 SSE 端点。"""
    url = f"{base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream"
    }
    
    try:
        print(f"🔍 测试 SSE {endpoint}")
        
        with httpx.Client(timeout=10.0) as client:
            with client.stream("GET", url, headers=headers) as response:
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ SSE 连接成功")
                    
                    # 读取前几个事件
                    event_count = 0
                    for line in response.iter_lines():
                        if line.strip():
                            print(f"   📋 事件: {line[:100]}...")
                            event_count += 1
                            if event_count >= 3:  # 只读取前3个事件
                                break
                    
                    return True
                else:
                    print(f"   ❌ SSE 连接失败: {response.status_code}")
                    print(f"   📋 错误: {response.text}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ SSE 请求失败: {e}")
        return False


def main():
    """主函数。"""
    print("🚀 开始测试 JWT 认证的 API 端点...\n")
    
    # 加载环境变量
    env_vars = load_env_file()
    if not env_vars:
        print("❌ 无法加载 .env 文件")
        return 1
    
    # 创建测试 token
    token = create_test_jwt(env_vars)
    if not token:
        print("❌ 无法创建测试 token")
        return 1
    
    # API 基础 URL
    base_url = "http://localhost:8000"
    
    print(f"🔗 API 基础 URL: {base_url}")
    print(f"🔑 使用 token: {token[:20]}...\n")
    
    # 测试端点列表
    test_results = []
    
    # 测试基础端点
    test_results.append(test_api_endpoint(base_url, "/", token))
    
    # 测试用户信息端点
    test_results.append(test_api_endpoint(base_url, "/api/v1/me", token))
    
    # 测试消息创建端点
    message_data = {
        "content": "Hello, this is a test message",
        "conversation_id": "test-conversation-123"
    }
    test_results.append(test_api_endpoint(base_url, "/api/v1/messages", token, "POST", message_data))
    
    # 如果消息创建成功，测试 SSE 端点
    # 注意：这里使用一个示例 message_id，实际应用中应该使用上面创建的消息 ID
    test_message_id = "test-message-123"
    test_results.append(test_sse_endpoint(base_url, f"/api/v1/messages/{test_message_id}/events", token))
    
    print()
    
    # 总结
    success_count = sum(test_results)
    total_count = len(test_results)
    
    if success_count == total_count:
        print(f"🎉 所有测试通过！({success_count}/{total_count})")
        print("\n📝 JWT 认证配置完全正确，API 端点工作正常。")
        return 0
    else:
        print(f"⚠️  部分测试失败 ({success_count}/{total_count})")
        print("\n📝 可能的原因:")
        print("1. FastAPI 服务器未启动 (python run.py)")
        print("2. 数据库表未创建")
        print("3. JWT token 格式不正确")
        return 1


if __name__ == "__main__":
    sys.exit(main())
