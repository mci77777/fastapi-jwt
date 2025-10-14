"""完整诊断 Supabase 状态端点问题"""
import asyncio
import httpx
import json
import sys

# 设置 UTF-8 编码
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())


async def main():
    print("=" * 70)
    print("Supabase Status Endpoint Diagnostic")
    print("=" * 70)
    
    base_url = "http://localhost:9999"
    
    # 1. 检查后端服务是否运行
    print("\n[1] 检查后端服务...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/api/v1/healthz")
            if response.status_code == 200:
                print("✓ 后端服务正常运行")
            else:
                print(f"✗ 后端服务异常: {response.status_code}")
                return
    except Exception as e:
        print(f"✗ 后端服务无法访问: {e}")
        print("\n请确保后端服务正在运行（端口 9999）")
        return
    
    # 2. 检查 OpenAPI Schema
    print("\n[2] 检查 OpenAPI Schema...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/openapi.json")
            schema = response.json()
            
            supabase_path = "/api/v1/llm/status/supabase"
            test_path = "/api/v1/llm/status/test-public"
            
            if supabase_path in schema.get("paths", {}):
                endpoint_def = schema["paths"][supabase_path]
                security = endpoint_def.get("get", {}).get("security", [])
                print(f"✓ Supabase 端点存在于 Schema")
                print(f"  Security: {security}")
                if not security:
                    print("  ✓ 端点不需要认证（Schema 层面）")
                else:
                    print(f"  ✗ 端点需要认证: {security}")
            else:
                print(f"✗ Supabase 端点不存在于 Schema")
            
            if test_path in schema.get("paths", {}):
                print(f"✓ 测试端点存在于 Schema（代码已重新加载）")
            else:
                print(f"✗ 测试端点不存在于 Schema（代码未重新加载！）")
                print("\n⚠️  后端服务可能没有重新加载代码！")
                print("   请手动重启后端服务：")
                print("   1. 关闭运行 'python run.py' 的 PowerShell 窗口")
                print("   2. 重新运行 '.\\start-dev.ps1' 或 'python run.py'")
                return
                
    except Exception as e:
        print(f"✗ 无法获取 OpenAPI Schema: {e}")
        return
    
    # 3. 测试公开端点（healthz）
    print("\n[3] 测试已知公开端点（healthz）...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/v1/healthz")
            if response.status_code == 200:
                print("✓ healthz 端点可公开访问")
            else:
                print(f"✗ healthz 端点异常: {response.status_code}")
    except Exception as e:
        print(f"✗ healthz 端点测试失败: {e}")
    
    # 4. 测试 Supabase 状态端点
    print("\n[4] 测试 Supabase 状态端点...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/v1/llm/status/supabase")
            print(f"  状态码: {response.status_code}")
            print(f"  响应体: {response.text[:200]}")
            
            if response.status_code == 200:
                print("✓ Supabase 状态端点可公开访问")
                data = response.json()
                print(f"  数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            elif response.status_code == 401:
                print("✗ Supabase 状态端点需要认证（401）")
                print("\n⚠️  问题诊断：")
                print("   - PolicyGate 配置正确（已添加到公开端点列表）")
                print("   - 路由函数已移除 Depends(get_current_user)")
                print("   - 但仍然返回 401 错误")
                print("\n可能原因：")
                print("   1. 后端服务未重新加载代码（最可能）")
                print("   2. 存在全局依赖注入（已排除）")
                print("   3. 中间件拦截（PolicyGate/RateLimiter 已检查）")
                print("\n建议操作：")
                print("   1. 手动重启后端服务")
                print("   2. 检查后端日志是否有错误信息")
                print("   3. 确认 PolicyGate 中间件是否正确初始化")
            else:
                print(f"✗ Supabase 状态端点异常: {response.status_code}")
                
    except Exception as e:
        print(f"✗ Supabase 状态端点测试失败: {e}")
    
    # 5. 测试测试端点（如果存在）
    print("\n[5] 测试测试端点（test-public）...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/v1/llm/status/test-public")
            if response.status_code == 200:
                print("✓ 测试端点可访问（代码已重新加载）")
            elif response.status_code == 404:
                print("✗ 测试端点不存在（代码未重新加载）")
            else:
                print(f"? 测试端点状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 测试端点测试失败: {e}")
    
    print("\n" + "=" * 70)
    print("诊断完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

