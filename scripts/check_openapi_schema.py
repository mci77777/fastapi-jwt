"""检查 OpenAPI Schema 中的 Supabase 状态端点定义"""
import asyncio
import httpx
import json


async def check_schema():
    """检查 OpenAPI Schema"""
    url = "http://localhost:9999/openapi.json"
    
    print("=" * 60)
    print("Checking OpenAPI Schema")
    print("=" * 60)
    print(f"URL: {url}\n")
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            schema = response.json()
            
            # 查找 Supabase 状态端点
            supabase_path = "/api/v1/llm/status/supabase"
            
            if supabase_path in schema.get("paths", {}):
                endpoint_def = schema["paths"][supabase_path]
                print(f"[FOUND] Endpoint: {supabase_path}")
                print(f"\nDefinition:")
                print(json.dumps(endpoint_def, indent=2, ensure_ascii=False))
                
                # 检查是否需要认证
                get_method = endpoint_def.get("get", {})
                security = get_method.get("security", [])
                
                print(f"\nSecurity Requirements: {security}")
                
                if not security:
                    print("\n[OK] Endpoint does NOT require authentication")
                else:
                    print(f"\n[WARNING] Endpoint requires authentication: {security}")
                
                return True
            else:
                print(f"[ERROR] Endpoint not found: {supabase_path}")
                print(f"\nAvailable paths:")
                for path in sorted(schema.get("paths", {}).keys()):
                    if "supabase" in path.lower():
                        print(f"  - {path}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to fetch schema: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    asyncio.run(check_schema())

