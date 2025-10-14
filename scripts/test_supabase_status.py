"""测试 Supabase 状态检查端点"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:9999"
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


async def test_supabase_status():
    """测试 Supabase 状态端点（无需认证）"""
    print("=" * 60)
    print("测试 Supabase 状态端点（无需认证）")
    print("=" * 60)

    url = f"{BASE_URL}/api/v1/llm/status/supabase"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            print(f"\n请求 URL: {url}")
            print("不携带认证 Token（测试公开访问）")

            response = await client.get(url)
            print(f"\n状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            print(f"\n响应体:")
            print(response.text)

            if response.status_code == 200:
                data = response.json()
                print(f"\n解析后的数据:")
                print(f"  状态: {data.get('data', {}).get('status')}")
                print(f"  详情: {data.get('data', {}).get('detail')}")
                print(f"  延迟: {data.get('data', {}).get('latency_ms')}ms")
                print(f"  最近同步: {data.get('data', {}).get('last_synced_at')}")
                print("\nOK - Supabase 状态端点正常")
                return True
            else:
                print(f"\nERROR - Supabase 状态端点异常")
                return False

        except Exception as e:
            print(f"\nERROR - Supabase 状态测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_supabase_direct():
    """直接测试 Supabase REST API"""
    print("\n" + "=" * 60)
    print("直接测试 Supabase REST API")
    print("=" * 60)
    
    project_id = os.getenv("SUPABASE_PROJECT_ID")
    base_url = f"https://{project_id}.supabase.co/rest/v1"
    
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # 测试 HEAD 请求（与后端实现一致）
            url = f"{base_url}/ai_model"
            print(f"\n请求 URL: {url}")
            print(f"方法: HEAD")
            
            response = await client.head(url, headers=headers, params={"limit": 1})
            print(f"\n状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("\nOK - Supabase REST API 可访问")
                return True
            else:
                print(f"\nERROR - Supabase REST API 返回异常状态码: {response.status_code}")
                return False

        except Exception as e:
            print(f"\nERROR - Supabase REST API 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_supabase_health():
    """测试 Supabase Health Check 端点"""
    print("\n" + "=" * 60)
    print("测试 Supabase Health Check 端点")
    print("=" * 60)
    
    project_id = os.getenv("SUPABASE_PROJECT_ID")
    
    # 根据 Supabase 官方文档，测试 GoTrue Health Check
    health_url = f"https://{project_id}.supabase.co/auth/v1/health"
    
    headers = {
        "apikey": os.getenv("SUPABASE_ANON_KEY"),
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            print(f"\n请求 URL: {health_url}")
            
            response = await client.get(health_url, headers=headers)
            print(f"\n状态码: {response.status_code}")
            print(f"响应体:")
            print(response.text)
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nGoTrue 版本: {data.get('version')}")
                print(f"服务名称: {data.get('name')}")
                print(f"描述: {data.get('description')}")
                print("\nOK - Supabase Health Check 正常")
                return True
            else:
                print(f"\nERROR - Supabase Health Check 异常")
                return False

        except Exception as e:
            print(f"\nERROR - Supabase Health Check 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """运行所有测试"""
    print("\n开始测试 Supabase 连接...\n")
    
    # 测试 1: 后端 API
    result1 = await test_supabase_status()
    
    # 测试 2: 直接测试 Supabase REST API
    result2 = await test_supabase_direct()
    
    # 测试 3: Supabase Health Check
    result3 = await test_supabase_health()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"后端 API: {'OK - 通过' if result1 else 'ERROR - 失败'}")
    print(f"Supabase REST API: {'OK - 通过' if result2 else 'ERROR - 失败'}")
    print(f"Supabase Health Check: {'OK - 通过' if result3 else 'ERROR - 失败'}")

    if all([result1, result2, result3]):
        print("\nOK - 所有测试通过")
    else:
        print("\nERROR - 部分测试失败，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())

