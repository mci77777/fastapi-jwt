#!/usr/bin/env python3
"""手动获取JWT token并测试API。"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

try:
    import httpx
except ImportError:
    print("❌ 需要安装依赖: pip install httpx")
    exit(1)


def load_env_file() -> Dict[str, str]:
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


def manual_confirm_and_login():
    """手动确认邮箱并登录获取JWT。"""
    print("🔍 手动确认邮箱并获取JWT token")

    # 从上面的测试中我们知道的信息
    test_email = "test1759121805@gymbro.cloud"
    test_password = "TestPassword123!"
    confirm_token = "3c5af27dea150a39ab2cd55214486f79ecbc387ae56676bca450e5b8"

    env_vars = load_env_file()
    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_anon_key = env_vars.get("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        print("❌ Supabase 配置不完整")
        return None

    try:
        with httpx.Client(timeout=30.0) as client:
            # 1. 先尝试确认邮箱
            print("🔗 确认邮箱...")
            confirm_url = f"{supabase_url}/auth/v1/verify?token={confirm_token}&type=signup"

            confirm_response = client.get(confirm_url)
            print(f"确认响应状态码: {confirm_response.status_code}")

            if confirm_response.status_code in [200, 302, 303]:
                print("✅ 邮箱确认成功")

                # 如果是303重定向，从响应中提取JWT token
                if confirm_response.status_code == 303:
                    response_text = confirm_response.text
                    print(f"📋 确认响应: {response_text[:200]}...")

                    # 从重定向URL中提取access_token
                    import re
                    token_match = re.search(r'access_token=([^&]+)', response_text)
                    if token_match:
                        jwt_token = token_match.group(1)
                        # URL解码
                        jwt_token = jwt_token.replace('%2B', '+').replace('%2F', '/').replace('%3D', '=')
                        print("✅ 从确认响应中提取到JWT token")
                        print(f"🔑 JWT Token: {jwt_token[:50]}...")
                        return jwt_token

                time.sleep(2)  # 等待确认生效

                # 2. 尝试登录获取JWT
                print("🔑 登录获取JWT token...")

                login_response = client.post(
                    f"{supabase_url}/auth/v1/token?grant_type=password",
                    headers={
                        "apikey": supabase_anon_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": test_email,
                        "password": test_password
                    }
                )

                print(f"登录响应状态码: {login_response.status_code}")

                if login_response.status_code == 200:
                    login_data = login_response.json()
                    jwt_token = login_data.get("access_token")
                    user_id = login_data.get("user", {}).get("id")

                    if jwt_token:
                        print("✅ 获取 JWT token 成功")
                        print(f"🆔 用户 ID: {user_id}")
                        print(f"📧 用户邮箱: {test_email}")
                        print(f"🔑 JWT Token: {jwt_token[:50]}...")
                        return jwt_token
                    else:
                        print("❌ 登录响应中没有 access_token")
                        print(f"响应内容: {login_data}")
                else:
                    print(f"❌ 登录失败: {login_response.text}")
            else:
                print(f"❌ 邮箱确认失败: {confirm_response.text}")

    except Exception as e:
        print(f"❌ 操作失败: {e}")

    return None


def test_api_with_jwt(jwt_token: str):
    """使用JWT token测试API。"""
    print("\n🧪 使用JWT token测试API")
    print("=" * 50)

    base_url = "http://localhost:9999"

    try:
        with httpx.Client(timeout=30.0) as client:
            # 测试消息创建
            print("📝 测试消息创建...")

            response = client.post(
                f"{base_url}/api/v1/messages",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": "hello",
                    "conversation_id": f"test-conv-{uuid.uuid4().hex[:8]}"
                }
            )

            print(f"状态码: {response.status_code}")
            trace_id = response.headers.get("x-trace-id", "N/A")
            print(f"Trace ID: {trace_id}")

            if response.status_code == 202:
                data = response.json()
                message_id = data.get("message_id")
                print(f"✅ 消息创建成功")
                print(f"📋 Message ID: {message_id}")

                # 测试SSE流
                if message_id:
                    print(f"\n📡 测试SSE事件流...")

                    sse_response = client.get(
                        f"{base_url}/api/v1/messages/{message_id}/events",
                        headers={
                            "Authorization": f"Bearer {jwt_token}",
                            "Accept": "text/event-stream"
                        },
                        timeout=30.0
                    )

                    print(f"SSE状态码: {sse_response.status_code}")

                    if sse_response.status_code == 200:
                        print("✅ SSE连接成功")

                        # 读取前几个事件
                        content = sse_response.text
                        lines = content.split('\n')[:10]  # 只显示前10行

                        for line in lines:
                            if line.strip():
                                print(f"📋 事件: {line[:100]}...")
                    else:
                        print(f"❌ SSE连接失败: {sse_response.text}")

                return True
            else:
                print(f"❌ 消息创建失败: {response.text}")
                return False

    except Exception as e:
        print(f"❌ API测试失败: {e}")
        return False


def query_database():
    """查询数据库验证数据写入。"""
    print("\n💾 查询数据库验证数据写入")
    print("=" * 50)

    env_vars = load_env_file()
    supabase_url = env_vars.get("SUPABASE_URL")
    service_role_key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
    chat_table = env_vars.get("SUPABASE_CHAT_TABLE", "ai_chat_messages")

    if not supabase_url or not service_role_key:
        print("❌ Supabase 配置不完整")
        return False

    try:
        with httpx.Client(timeout=15.0) as client:
            # 查询最近的消息
            table_url = f"{supabase_url}/rest/v1/{chat_table}"

            response = client.get(
                table_url,
                headers={
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "5", "order": "created_at.desc"}
            )

            if response.status_code == 200:
                records = response.json()
                print(f"✅ 数据库查询成功")
                print(f"📊 找到 {len(records)} 条记录")

                for i, record in enumerate(records[:3]):
                    # 脱敏处理
                    safe_record = {
                        "id": record.get("id", "N/A")[:8] + "...",
                        "role": record.get("role", "N/A"),
                        "content": record.get("content", "N/A")[:50] + "..." if len(record.get("content", "")) > 50 else record.get("content", "N/A"),
                        "created_at": record.get("created_at", "N/A")
                    }
                    print(f"   {i+1}. {safe_record}")

                return True
            else:
                print(f"❌ 数据库查询失败: {response.status_code}")
                print(f"响应: {response.text}")
                return False

    except Exception as e:
        print(f"❌ 数据库查询异常: {e}")
        return False


def main():
    """主函数。"""
    print("🚀 手动JWT测试和端到端验证\n")

    # 1. 获取JWT token
    jwt_token = manual_confirm_and_login()

    if not jwt_token:
        print("❌ 无法获取JWT token，测试终止")
        return 1

    # 2. 测试API
    api_success = test_api_with_jwt(jwt_token)

    # 3. 等待一下让数据写入完成
    if api_success:
        print("\n⏳ 等待数据写入完成...")
        time.sleep(5)

        # 4. 查询数据库
        db_success = query_database()

        if db_success:
            print("\n🎉 端到端测试完全成功！")
            return 0
        else:
            print("\n⚠️  API测试成功，但数据库验证失败")
            return 1
    else:
        print("\n❌ API测试失败")
        return 1


if __name__ == "__main__":
    exit(main())
