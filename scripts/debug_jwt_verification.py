#!/usr/bin/env python3
"""
调试 JWT 验证过程
"""

import json
import os
import sys
import time

import jwt

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


def test_jwt_verification():
    """测试 JWT 验证过程"""
    print("🔍 JWT 验证调试")
    print("=" * 50)
    
    settings = get_settings()
    
    # 显示配置
    print("📋 当前配置:")
    print(f"   JWK: {settings.supabase_jwk}")
    print(f"   Issuer: {settings.supabase_issuer}")
    print(f"   Audience: {settings.supabase_audience}")
    
    # 获取 Service Role Key
    service_key = settings.supabase_service_role_key
    print(f"\n🔑 Service Role Key: {service_key[:50]}...")
    
    # 解析 JWK
    try:
        jwk_data = json.loads(settings.supabase_jwk)
        print(f"\n📋 JWK 数据:")
        print(json.dumps(jwk_data, indent=2))
        
        # 创建密钥对象
        algorithm_cls = jwt.algorithms.get_default_algorithms()['HS256']
        public_key = algorithm_cls.from_jwk(json.dumps(jwk_data))
        print(f"\n🔐 密钥对象创建成功: {type(public_key)}")
        
    except Exception as e:
        print(f"\n❌ JWK 解析失败: {e}")
        return False
    
    # 尝试验证 JWT
    try:
        print(f"\n🔍 开始验证 JWT...")
        
        # 获取 JWT 头部
        header = jwt.get_unverified_header(service_key)
        print(f"   JWT 头部: {header}")
        
        # 验证参数
        audience = settings.supabase_audience or None
        issuer = str(settings.supabase_issuer) if settings.supabase_issuer else None
        
        print(f"   期望签发者: {issuer}")
        print(f"   期望受众: {audience}")
        
        # 设置验证选项
        options = {
            "require": ["iss", "sub", "exp", "iat"],
            "verify_aud": bool(audience),
        }
        
        print(f"   验证选项: {options}")
        
        # 执行验证
        payload = jwt.decode(
            service_key,
            key=public_key,
            algorithms=['HS256'],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options=options,
        )
        
        print(f"\n✅ JWT 验证成功!")
        print(f"📋 Payload:")
        print(json.dumps(payload, indent=2))
        
        return True
        
    except jwt.InvalidSignatureError as e:
        print(f"\n❌ 签名验证失败: {e}")
        
        # 尝试不同的密钥
        print("\n🔧 尝试调试签名问题...")
        
        # 检查原始密钥
        original_secret = "sb_secret_JZba0OSzvqEYVJADziEazg_HG3u57I3"
        print(f"   原始密钥: {original_secret}")
        
        try:
            payload = jwt.decode(
                service_key,
                key=original_secret,
                algorithms=['HS256'],
                audience=audience,
                issuer=issuer,
                leeway=30,
                options=options,
            )
            print(f"   ✅ 使用原始密钥验证成功!")
            print(f"   💡 建议: 直接使用原始密钥而不是 JWK")
            return True
            
        except Exception as e2:
            print(f"   ❌ 使用原始密钥也失败: {e2}")
        
        return False
        
    except jwt.InvalidIssuerError as e:
        print(f"\n❌ 签发者验证失败: {e}")
        
        # 尝试不验证签发者
        try:
            payload = jwt.decode(
                service_key,
                key=public_key,
                algorithms=['HS256'],
                audience=audience,
                issuer=None,  # 不验证签发者
                leeway=30,
                options={
                    "require": ["sub", "exp", "iat"],
                    "verify_aud": bool(audience),
                    "verify_iss": False,
                },
            )
            print(f"   ✅ 跳过签发者验证后成功!")
            print(f"   💡 建议: 配置正确的签发者或跳过验证")
            return True
            
        except Exception as e2:
            print(f"   ❌ 跳过签发者验证也失败: {e2}")
        
        return False
        
    except jwt.InvalidAudienceError as e:
        print(f"\n❌ 受众验证失败: {e}")
        
        # 尝试不验证受众
        try:
            payload = jwt.decode(
                service_key,
                key=public_key,
                algorithms=['HS256'],
                audience=None,  # 不验证受众
                issuer=issuer,
                leeway=30,
                options={
                    "require": ["iss", "sub", "exp", "iat"],
                    "verify_aud": False,
                },
            )
            print(f"   ✅ 跳过受众验证后成功!")
            print(f"   💡 建议: 配置正确的受众或跳过验证")
            return True
            
        except Exception as e2:
            print(f"   ❌ 跳过受众验证也失败: {e2}")
        
        return False
        
    except Exception as e:
        print(f"\n❌ JWT 验证失败: {e}")
        return False


def main():
    """主函数"""
    success = test_jwt_verification()
    
    if success:
        print(f"\n🎉 JWT 验证调试完成 - 找到可行方案!")
    else:
        print(f"\n⚠️  JWT 验证调试失败 - 需要进一步排查")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
