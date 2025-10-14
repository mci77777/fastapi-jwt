"""最终验证 Supabase 状态端点"""
import asyncio
import httpx
import sys
import codecs

if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())


async def main():
    print("=" * 60)
    print("Supabase 状态端点 - 最终验证")
    print("=" * 60)
    
    url = "http://localhost:9999/api/v1/llm/status/supabase"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            
            print(f"\n请求 URL: {url}")
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ 成功！Supabase 状态端点正常工作")
                print(f"\n响应数据：")
                print(f"  状态: {data.get('data', {}).get('status')}")
                print(f"  详情: {data.get('data', {}).get('detail')}")
                print(f"  延迟: {data.get('data', {}).get('latency_ms'):.2f} ms")
                print(f"  最近同步: {data.get('data', {}).get('last_synced_at')}")
                
                print(f"\n下一步：")
                print(f"  1. 打开浏览器访问: http://localhost:3101/dashboard")
                print(f"  2. 查看 Supabase 状态卡片")
                print(f"  3. 应该显示：状态=在线，延迟={data.get('data', {}).get('latency_ms'):.2f}ms")
                
                return True
            else:
                print(f"\n❌ 失败！状态码: {response.status_code}")
                print(f"响应体: {response.text}")
                return False
                
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

