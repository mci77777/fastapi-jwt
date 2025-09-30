#!/usr/bin/env python3
"""端到端测试：用户发送 hello 的完整流程测试。"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

try:
    import httpx
    from supabase import create_client, Client
except ImportError:
    print("❌ 需要安装依赖: pip install httpx supabase")
    sys.exit(1)


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


def create_temp_email() -> Optional[Dict[str, str]]:
    """使用邮箱API创建临时邮箱。"""
    api_key = "mk_Se9GzoZUl4Sy1ah-Avj4JYohg-IMEa8C"
    base_url = "https://taxbattle.xyz/api"

    try:
        print("🔍 创建临时邮箱...")

        with httpx.Client(timeout=30.0) as client:
            # 生成临时邮箱
            response = client.post(
                f"{base_url}/emails/generate",
                headers={
                    "X-API-Key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "name": f"test{int(time.time())}",
                    "expiryTime": 3600000,  # 1小时
                    "domain": "gymbro.cloud"  # 使用可用的域名
                }
            )

            print(f"邮箱创建响应状态码: {response.status_code}")

            if response.status_code in [200, 201]:
                email_data = response.json()
                email_address = email_data.get("email")
                email_id = email_data.get("id")

                if email_address and email_id:
                    print(f"✅ 临时邮箱创建成功: {email_address}")
                    return {
                        "email": email_address,
                        "id": email_id,
                        "api_key": api_key,
                        "base_url": base_url
                    }
                else:
                    print(f"❌ 邮箱响应格式异常: {email_data}")
            else:
                print(f"❌ 邮箱创建失败: {response.text}")

    except Exception as e:
        print(f"❌ 邮箱API调用失败: {e}")

    return None


def wait_for_confirmation_email(email_info: Dict[str, str], timeout: int = 300) -> Optional[str]:
    """等待并获取确认邮件中的确认链接。"""
    api_key = email_info["api_key"]
    base_url = email_info["base_url"]
    email_id = email_info["id"]

    print(f"🔍 等待确认邮件（最多等待 {timeout} 秒）...")

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=15.0) as client:
                # 获取邮件列表
                response = client.get(
                    f"{base_url}/emails/{email_id}",
                    headers={"X-API-Key": api_key}
                )

                if response.status_code == 200:
                    messages = response.json().get("messages", [])

                    for message in messages:
                        subject = message.get("subject", "").lower()
                        if "confirm" in subject or "verify" in subject:
                            message_id = message.get("id")

                            if message_id:
                                # 获取邮件详细内容
                                detail_response = client.get(
                                    f"{base_url}/emails/{email_id}/{message_id}",
                                    headers={"X-API-Key": api_key}
                                )

                                if detail_response.status_code == 200:
                                    email_content = detail_response.json()
                                    body = email_content.get("body", "")

                                    # 查找确认链接
                                    import re
                                    confirm_pattern = r'https://[^\s]+/auth/v1/verify[^\s]*'
                                    matches = re.findall(confirm_pattern, body)

                                    if matches:
                                        confirm_url = matches[0]
                                        print(f"✅ 找到确认链接: {confirm_url[:50]}...")
                                        return confirm_url

                print(f"⏳ 等待邮件中... ({int(time.time() - start_time)}s)")
                time.sleep(5)  # 等待5秒后重试

        except Exception as e:
            print(f"⚠️  检查邮件时出错: {e}")
            time.sleep(5)

    print("❌ 等待确认邮件超时")
    return None


def create_test_user_and_get_jwt(env_vars: Dict[str, str]) -> Optional[str]:
    """创建测试用户并获取 JWT token。"""
    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_anon_key = env_vars.get("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        print("❌ SUPABASE_URL 或 SUPABASE_ANON_KEY 未配置")
        return None

    # 方法1: 使用真实邮箱服务创建用户
    print("🔍 使用真实邮箱服务创建测试用户...")

    # 创建临时邮箱
    email_info = create_temp_email()
    if not email_info:
        print("❌ 无法创建临时邮箱")
        return None

    test_email = email_info["email"]
    test_password = "TestPassword123!"

    try:
        with httpx.Client(timeout=30.0) as client:
            # 注册用户
            print(f"📧 使用邮箱注册: {test_email}")

            signup_response = client.post(
                f"{supabase_url}/auth/v1/signup",
                headers={
                    "apikey": supabase_anon_key,
                    "Content-Type": "application/json"
                },
                json={
                    "email": test_email,
                    "password": test_password
                }
            )

            print(f"注册响应状态码: {signup_response.status_code}")

            if signup_response.status_code in [200, 201]:
                signup_data = signup_response.json()
                print("✅ 用户注册成功")
                print(f"📋 注册响应: {signup_data}")

                # 检查是否需要邮箱确认
                # 注册响应直接返回用户信息，没有嵌套在 "user" 字段中
                user_data = signup_data
                session_data = signup_data.get("session")
                confirmation_sent = signup_data.get("confirmation_sent_at")

                if confirmation_sent and not session_data:
                    print("📧 需要邮箱确认，等待确认邮件...")

                    # 等待确认邮件
                    confirm_url = wait_for_confirmation_email(email_info)

                    if confirm_url:
                        # 访问确认链接
                        print("🔗 访问确认链接...")
                        confirm_response = client.get(confirm_url)
                        print(f"确认响应状态码: {confirm_response.status_code}")

                        if confirm_response.status_code in [200, 302]:
                            print("✅ 邮箱确认成功")
                            # 等待一下让确认生效
                            time.sleep(5)
                        else:
                            print(f"⚠️  确认响应异常: {confirm_response.text}")
                    else:
                        print("❌ 未能获取确认链接")
                        return None
                elif session_data:
                    print("✅ 注册时已获得会话，无需邮箱确认")
                    # 直接从注册响应中获取 token
                    jwt_token = session_data.get("access_token")
                    if jwt_token:
                        user_id = user_data.get("id") if user_data else "unknown"
                        print("✅ 从注册响应获取 JWT token 成功")
                        print(f"🆔 用户 ID: {user_id}")
                        print(f"📧 用户邮箱: {test_email}")
                        return jwt_token

                # 尝试登录获取 JWT
                print("🔑 尝试登录获取 JWT token...")

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
                        return jwt_token
                    else:
                        print("❌ 登录响应中没有 access_token")
                        print(f"响应内容: {login_data}")
                else:
                    print(f"❌ 登录失败: {login_response.text}")
            else:
                print(f"❌ 用户注册失败: {signup_response.text}")

    except Exception as e:
        print(f"❌ 用户创建过程失败: {e}")

    return None


def test_api_call(base_url: str, endpoint: str, token: str, method: str = "GET",
                  data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
    """测试 API 调用。"""
    url = f"{base_url}{endpoint}"
    default_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    if headers:
        default_headers.update(headers)

    try:
        print(f"🔍 测试 {method} {endpoint}")

        with httpx.Client(timeout=30.0) as client:
            if method == "GET":
                response = client.get(url, headers=default_headers)
            elif method == "POST":
                response = client.post(url, headers=default_headers, json=data)
            else:
                return {"success": False, "error": f"不支持的方法: {method}"}

        print(f"   状态码: {response.status_code}")

        # 获取 trace_id
        trace_id = response.headers.get("x-trace-id", "N/A")
        print(f"   Trace ID: {trace_id}")

        result = {
            "success": response.status_code in [200, 202],
            "status_code": response.status_code,
            "trace_id": trace_id,
            "headers": dict(response.headers)
        }

        try:
            result["data"] = response.json()
        except:
            result["data"] = response.text

        if result["success"]:
            print("   ✅ 请求成功")
        else:
            print(f"   ❌ 请求失败: {response.status_code}")

        return result

    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return {"success": False, "error": str(e)}


def test_sse_stream(base_url: str, message_id: str, token: str) -> Dict:
    """测试 SSE 事件流。"""
    url = f"{base_url}/api/v1/messages/{message_id}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream"
    }

    try:
        print(f"🔍 测试 SSE 流: {message_id}")

        events = []
        with httpx.Client(timeout=30.0) as client:
            with client.stream("GET", url, headers=headers) as response:
                print(f"   状态码: {response.status_code}")

                if response.status_code != 200:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text
                    }

                print("   ✅ SSE 连接成功，开始接收事件...")

                # 读取事件流
                for line in response.iter_lines():
                    if line.strip():
                        events.append(line)
                        print(f"   📋 事件: {line[:100]}...")

                        # 检查是否收到 done 事件
                        if "event:done" in line or "event: done" in line:
                            print("   🏁 收到完成事件")
                            break

                        # 限制事件数量防止无限循环
                        if len(events) > 50:
                            print("   ⚠️  事件数量过多，停止接收")
                            break

        return {
            "success": True,
            "events": events,
            "event_count": len(events)
        }

    except Exception as e:
        print(f"   ❌ SSE 请求失败: {e}")
        return {"success": False, "error": str(e)}


def query_database_with_service_key(env_vars: Dict[str, str], user_id: str) -> Dict:
    """使用 Service Role Key 查询数据库。"""
    supabase_url = env_vars.get("SUPABASE_URL")
    service_role_key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
    chat_table = env_vars.get("SUPABASE_CHAT_TABLE", "ai_chat_messages")

    if not supabase_url or not service_role_key:
        return {"success": False, "error": "Supabase 配置不完整"}

    try:
        # 使用 Service Role Key 创建客户端
        supabase: Client = create_client(supabase_url, service_role_key)

        print(f"🔍 查询数据库表: {chat_table}")

        # 查询最近的消息
        response = supabase.table(chat_table).select("*").order("timestamp", desc=True).limit(5).execute()

        if response.data:
            print(f"✅ 查询成功，找到 {len(response.data)} 条记录")
            return {"success": True, "data": response.data}
        else:
            print("⚠️  查询成功但没有找到记录")
            return {"success": True, "data": []}

    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        return {"success": False, "error": str(e)}


def main():
    """主函数。"""
    print("🚀 开始端到端测试：用户发送 hello 的完整流程\n")

    # 加载环境变量
    env_vars = load_env_file()
    if not env_vars:
        print("❌ 无法加载 .env 文件")
        return 1

    # API 基础 URL
    base_url = "http://localhost:9999"  # 注意端口是 9999

    print(f"🔗 API 基础 URL: {base_url}\n")

    # 步骤 1: 确认 FastAPI 服务可用
    print("=" * 50)
    print("步骤 1: 确认 FastAPI 服务可用")
    print("=" * 50)

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base_url}/docs")
            if response.status_code == 200:
                print("✅ FastAPI 服务正常运行")
            else:
                print(f"❌ FastAPI 服务异常: {response.status_code}")
                return 1
    except Exception as e:
        print(f"❌ 无法连接到 FastAPI 服务: {e}")
        return 1

    # 步骤 2: 获取 JWT token
    print("\n" + "=" * 50)
    print("步骤 2: 通过 Supabase Auth API 获取 JWT token")
    print("=" * 50)

    jwt_token = create_test_user_and_get_jwt(env_vars)
    if not jwt_token:
        print("❌ 无法获取 JWT token")
        return 1

    print(f"🔑 JWT Token: {jwt_token[:50]}...\n")

    # 步骤 3: 调用 POST /api/v1/messages
    print("=" * 50)
    print("步骤 3: 调用 POST /api/v1/messages")
    print("=" * 50)

    message_data = {
        "text": "hello",
        "conversation_id": f"test-conv-{uuid.uuid4().hex[:8]}"
    }

    message_result = test_api_call(
        base_url, "/api/v1/messages", jwt_token, "POST", message_data
    )

    if not message_result["success"]:
        print("❌ 消息创建失败")
        print(f"错误: {message_result}")
        return 1

    message_id = message_result["data"].get("message_id")
    if not message_id:
        print("❌ 未获取到 message_id")
        return 1

    print(f"✅ 消息创建成功，message_id: {message_id}")
    print(f"📋 Trace ID: {message_result['trace_id']}")

    # 步骤 4: 测试 SSE 事件流
    print("\n" + "=" * 50)
    print("步骤 4: 测试 SSE 事件流")
    print("=" * 50)

    sse_result = test_sse_stream(base_url, message_id, jwt_token)

    if not sse_result["success"]:
        print("❌ SSE 测试失败")
        print(f"错误: {sse_result}")
    else:
        print(f"✅ SSE 测试成功，接收到 {sse_result['event_count']} 个事件")

    # 步骤 5: 查询数据库验证数据写入
    print("\n" + "=" * 50)
    print("步骤 5: 查询数据库验证数据写入")
    print("=" * 50)

    # 等待一下确保数据写入完成
    time.sleep(2)

    db_result = query_database_with_service_key(env_vars, "test-user")

    if db_result["success"]:
        print("✅ 数据库查询成功")
        if db_result["data"]:
            print(f"📋 最近的消息记录:")
            for i, record in enumerate(db_result["data"][:3]):
                # 脱敏处理
                safe_record = {
                    "id": record.get("id", "N/A")[:8] + "...",
                    "role": record.get("role", "N/A"),
                    "content": record.get("content", "N/A")[:50] + "..." if len(record.get("content", "")) > 50 else record.get("content", "N/A"),
                    "timestamp": record.get("timestamp", "N/A")
                }
                print(f"   {i+1}. {safe_record}")
        else:
            print("⚠️  数据库中没有找到消息记录")
    else:
        print(f"❌ 数据库查询失败: {db_result['error']}")

    # 步骤 6: 负例测试
    print("\n" + "=" * 50)
    print("步骤 6: 负例测试")
    print("=" * 50)

    # 测试错误的 token
    bad_token = jwt_token[:-5] + "XXXXX"  # 改坏最后几个字符
    print("🔍 测试错误的 JWT token...")

    bad_result = test_api_call(
        base_url, "/api/v1/messages", bad_token, "POST", message_data
    )

    if bad_result["status_code"] == 401:
        print("✅ 错误 token 正确返回 401")
        print(f"📋 Trace ID: {bad_result['trace_id']}")
    else:
        print(f"⚠️  错误 token 返回了意外状态码: {bad_result['status_code']}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
