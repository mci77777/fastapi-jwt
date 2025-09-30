#!/usr/bin/env python3
"""
解码 JWT 令牌以查看其结构
"""

import base64
import json
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


def decode_jwt_without_verification(token: str):
    """解码 JWT 而不验证签名"""
    try:
        # 分割 JWT
        parts = token.split('.')
        if len(parts) != 3:
            print("❌ JWT 格式无效")
            return None, None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # 解码 header
        header_padding = '=' * (4 - len(header_b64) % 4)
        header_bytes = base64.urlsafe_b64decode(header_b64 + header_padding)
        header = json.loads(header_bytes)
        
        # 解码 payload
        payload_padding = '=' * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + payload_padding)
        payload = json.loads(payload_bytes)
        
        return header, payload
        
    except Exception as e:
        print(f"❌ 解码失败: {e}")
        return None, None


def main():
    """主函数"""
    print("🔍 JWT 令牌解码工具")
    print("=" * 50)
    
    settings = get_settings()
    service_key = settings.supabase_service_role_key
    
    if not service_key:
        print("❌ 未找到 Service Role Key")
        return
    
    print(f"🔑 Service Role Key 长度: {len(service_key)}")
    print(f"🔑 前缀: {service_key[:20]}...")
    
    header, payload = decode_jwt_without_verification(service_key)
    
    if header:
        print(f"\n📋 JWT Header:")
        print(json.dumps(header, indent=2, ensure_ascii=False))
        
        print(f"\n📋 JWT Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
        # 分析关键字段
        print(f"\n🔍 关键信息:")
        print(f"   算法: {header.get('alg')}")
        print(f"   密钥ID: {header.get('kid')}")
        print(f"   签发者: {payload.get('iss')}")
        print(f"   受众: {payload.get('aud')}")
        print(f"   角色: {payload.get('role')}")
        print(f"   项目引用: {payload.get('ref')}")
        
        # 检查是否匹配配置
        print(f"\n✅ 配置匹配检查:")
        expected_issuer = str(settings.supabase_issuer) if settings.supabase_issuer else None
        expected_audience = settings.supabase_audience
        
        if expected_issuer and payload.get('iss') == expected_issuer:
            print(f"   ✅ 签发者匹配: {payload.get('iss')}")
        else:
            print(f"   ❌ 签发者不匹配:")
            print(f"      期望: {expected_issuer}")
            print(f"      实际: {payload.get('iss')}")
        
        if expected_audience and payload.get('aud') == expected_audience:
            print(f"   ✅ 受众匹配: {payload.get('aud')}")
        else:
            print(f"   ❌ 受众不匹配:")
            print(f"      期望: {expected_audience}")
            print(f"      实际: {payload.get('aud')}")
        
        # 建议配置修正
        if payload.get('iss') != expected_issuer or payload.get('aud') != expected_audience:
            print(f"\n💡 建议的配置修正:")
            if payload.get('iss'):
                print(f"   SUPABASE_ISSUER={payload.get('iss')}")
            if payload.get('aud'):
                print(f"   SUPABASE_AUDIENCE={payload.get('aud')}")
    
    else:
        print("❌ 无法解码 JWT")


if __name__ == "__main__":
    main()
