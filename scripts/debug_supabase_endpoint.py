"""调试 Supabase 状态端点"""
import asyncio
import httpx
import json


async def test_endpoint():
    """测试端点"""
    url = "http://localhost:9999/api/v1/llm/status/supabase"
    
    print("=" * 60)
    print("DEBUG: Supabase Status Endpoint")
    print("=" * 60)
    print(f"URL: {url}")
    print("Method: GET")
    print("Headers: None (testing public access)")
    print("")
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            
            print(f"Status Code: {response.status_code}")
            print(f"\nResponse Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            
            print(f"\nResponse Body:")
            try:
                data = response.json()
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(response.text)
            
            if response.status_code == 200:
                print("\n[OK] Endpoint is accessible")
                return True
            else:
                print(f"\n[ERROR] Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"\n[ERROR] Request failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    asyncio.run(test_endpoint())

