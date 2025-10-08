#!/usr/bin/env python3
"""测试 Web 前端服务"""
import httpx
import sys


def test_frontend():
    """测试前端服务"""
    print("=" * 60)
    print("测试 Web 前端服务")
    print("=" * 60)
    
    url = "http://localhost:3100/"
    
    try:
        print(f"\n正在访问: {url}")
        response = httpx.get(url, timeout=10, follow_redirects=True)
        
        print(f"\n状态码: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"内容长度: {len(response.text)} bytes")
        
        # 检查是否包含 Vue 应用的标志
        if 'id="app"' in response.text or 'id="root"' in response.text:
            print("\n[OK] 前端页面加载成功 - 找到 Vue 应用容器")
        else:
            print("\n[WARN] 前端页面加载,但未找到 Vue 应用容器")

        # 检查是否有错误
        if response.status_code == 200:
            print("\n[OK] 前端服务运行正常")
            return 0
        else:
            print(f"\n[FAIL] 前端服务返回错误状态码: {response.status_code}")
            return 1

    except httpx.ConnectError:
        print(f"\n[FAIL] 无法连接到前端服务: {url}")
        print("请确保前端服务已启动: pnpm dev")
        return 1
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return 1


def test_api_proxy():
    """测试 API 代理"""
    print("\n" + "=" * 60)
    print("测试 API 代理")
    print("=" * 60)
    
    url = "http://localhost:3100/api/v1/healthz"
    
    try:
        print(f"\n正在访问: {url}")
        response = httpx.get(url, timeout=10)
        
        print(f"\n状态码: {response.status_code}")
        print(f"响应内容: {response.text[:200]}")
        
        if response.status_code == 200:
            print("\n[OK] API 代理工作正常")
            return 0
        else:
            print(f"\n[FAIL] API 代理返回错误状态码: {response.status_code}")
            return 1

    except Exception as e:
        print(f"\n[FAIL] API 代理测试失败: {e}")
        return 1


def main():
    """主函数"""
    result1 = test_frontend()
    result2 = test_api_proxy()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if result1 == 0 and result2 == 0:
        print("\n[SUCCESS] 所有测试通过")
        print("\n前端服务地址: http://localhost:3100/")
        print("API 代理地址: http://localhost:3100/api/v1/")
        return 0
    else:
        print("\n[FAIL] 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

