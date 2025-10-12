#!/usr/bin/env python3
"""自动登录并获取 JWT token"""
import sys
import requests
import json

def main():
    print("=" * 80)
    print("自动登录测试")
    print("=" * 80)
    
    # 1. 登录
    print("\n[1] 正在登录...")
    print("  用户名: admin")
    print("  密码: 123456")
    
    try:
        response = requests.post(
            'http://localhost:9999/api/v1/base/access_token',
            json={'username': 'admin', 'password': '123456'},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"  ❌ 登录失败: HTTP {response.status_code}")
            print(f"  响应: {response.text}")
            return 1
        
        data = response.json()
        if data.get('code') != 200:
            print(f"  ❌ 登录失败: {data.get('msg')}")
            return 1
        
        token = data['data']['access_token']
        print(f"  ✅ 登录成功！")
        print(f"  Token 长度: {len(token)}")
        
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 无法连接到后端服务 (http://localhost:9999)")
        print(f"  请确保后端服务正在运行")
        return 1
    except Exception as e:
        print(f"  ❌ 登录失败: {e}")
        return 1
    
    # 2. 解码 token
    print(f"\n[2] 解码 Token")
    try:
        import jwt
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        
        print(f"  Header:")
        print(f"    算法: {header.get('alg')}")
        print(f"    类型: {header.get('typ')}")
        
        print(f"  Payload:")
        print(f"    签发者: {payload.get('iss')}")
        print(f"    用户ID: {payload.get('sub')}")
        print(f"    受众: {payload.get('aud')}")
        print(f"    邮箱: {payload.get('email')}")
        print(f"    角色: {payload.get('role')}")
        
        # 检查过期时间
        import time
        exp = payload.get('exp')
        if exp:
            exp_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))
            remaining = exp - int(time.time())
            print(f"    过期时间: {exp_time} (剩余 {remaining//60} 分钟)")
        
    except Exception as e:
        print(f"  ⚠️  解码失败: {e}")
    
    # 3. 验证 token
    print(f"\n[3] 验证 Token")
    try:
        from app.auth.jwt_verifier import get_jwt_verifier
        verifier = get_jwt_verifier()
        user = verifier.verify_token(token)
        print(f"  ✅ Token 验证成功！")
        print(f"    用户ID: {user.uid}")
        print(f"    用户类型: {user.user_type}")
    except Exception as e:
        print(f"  ❌ Token 验证失败: {e}")
    
    # 4. 输出 token（用于复制）
    print(f"\n[4] Token 输出")
    print(f"  完整 Token:")
    print(f"  {token}")
    
    print(f"\n[5] 使用方法")
    print(f"  方法 1 - 浏览器控制台:")
    print(f"    localStorage.setItem('ACCESS_TOKEN', JSON.stringify({{value: '{token[:50]}...'}}))")
    
    print(f"\n  方法 2 - WebSocket 测试:")
    print(f"    const ws = new WebSocket('ws://localhost:9999/api/v1/ws/dashboard?token={token[:50]}...')")
    
    print(f"\n  方法 3 - 命令行验证:")
    print(f"    python scripts/tmp_verify_es256_jwt.py {token[:50]}...")
    
    print("\n" + "=" * 80)
    print("✅ 登录成功！Token 已生成")
    print("=" * 80)
    
    # 保存到文件（可选）
    try:
        with open('scripts/.last_token.txt', 'w') as f:
            f.write(token)
        print("\n💾 Token 已保存到: scripts/.last_token.txt")
    except Exception as e:
        print(f"\n⚠️  保存 token 失败: {e}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

