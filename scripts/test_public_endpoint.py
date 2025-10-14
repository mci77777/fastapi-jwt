"""测试公开端点"""
import asyncio
import httpx


async def test():
    url = "http://localhost:9999/api/v1/llm/status/test-public"
    
    print(f"Testing: {url}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        if response.status_code == 200:
            print("\n[OK] Public endpoint works!")
            return True
        else:
            print(f"\n[ERROR] Status code: {response.status_code}")
            return False


if __name__ == "__main__":
    asyncio.run(test())

