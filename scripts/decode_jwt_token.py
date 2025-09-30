#!/usr/bin/env python3
"""解码JWT token查看其内容。"""

import base64
import json
import sys

def decode_jwt_token(token: str):
    """解码JWT token。"""
    try:
        # JWT token由三部分组成：header.payload.signature
        parts = token.split('.')
        
        if len(parts) != 3:
            print("❌ JWT token格式不正确")
            return
        
        header_b64, payload_b64, signature_b64 = parts
        
        # 解码header
        header_padding = '=' * (4 - len(header_b64) % 4)
        header_bytes = base64.urlsafe_b64decode(header_b64 + header_padding)
        header = json.loads(header_bytes.decode('utf-8'))
        
        # 解码payload
        payload_padding = '=' * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + payload_padding)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        print("🔍 JWT Token 解码结果:")
        print("=" * 50)
        
        print("📋 Header:")
        print(json.dumps(header, indent=2, ensure_ascii=False))
        
        print("\n📋 Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
        print(f"\n📋 Signature: {signature_b64[:50]}...")
        
        # 检查关键字段
        print("\n🔍 关键字段检查:")
        print(f"   算法 (alg): {header.get('alg', 'N/A')}")
        print(f"   密钥ID (kid): {header.get('kid', 'N/A')}")
        print(f"   发行者 (iss): {payload.get('iss', 'N/A')}")
        print(f"   受众 (aud): {payload.get('aud', 'N/A')}")
        print(f"   主题 (sub): {payload.get('sub', 'N/A')}")
        print(f"   邮箱 (email): {payload.get('email', 'N/A')}")
        
        # 检查过期时间
        exp = payload.get('exp')
        if exp:
            import time
            current_time = int(time.time())
            if exp > current_time:
                remaining = exp - current_time
                print(f"   过期时间: {remaining} 秒后过期")
            else:
                print(f"   ⚠️  Token已过期 ({current_time - exp} 秒前)")
        
    except Exception as e:
        print(f"❌ 解码失败: {e}")


def main():
    """主函数。"""
    # 从测试中获得的JWT token
    jwt_token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI5NmU2Y2E5LTk3MzMtNDgzZi1iNGJiLTcwMzliMzEwMmM5MiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3J5a2dsaXZyd3pjeWtoaG54d296LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI3N2MxNmY1My02NGQwLTQyNGItYjliZS1iOTQyYmI2ZTkyZmUiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTI1Nzk0LCJpYXQiOjE3NTkxMjIxOTQsImVtYWlsIjoidGVzdDE3NTkxMjE4MDVAZ3ltYnJvLmNsb3VkIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6InRlc3QxNzU5MTIxODA1QGd5bWJyby5jbG91ZCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6Ijc3YzE2ZjUzLTY0ZDAtNDI0Yi1iOWJlLWI5NDJiYjZlOTJmZSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im90cCIsInRpbWVzdGFtcCI6MTc1OTEyMjE5NH1dLCJzZXNzaW9uX2lkIjoiZjFhZjZlOGYtYWNmMC00ZDA0LWIzNzgtYzU2ZDNlYTkxNmIyIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.zS7NZRVU74CZLUzMFS5E1DITTUN5MbV_B9upO6L1JoSDvhHJYpdYjXLnf4RBuMoMLHHoxLLYR1dXaf63jwDrwg"
    
    print("🚀 JWT Token 解码工具\n")
    decode_jwt_token(jwt_token)


if __name__ == "__main__":
    main()
