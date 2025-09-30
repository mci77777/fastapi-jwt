#!/usr/bin/env python3
"""
为 HS256 JWT 创建 JWK
"""

import base64
import json
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def create_hs256_jwk(secret: str) -> str:
    """为 HS256 创建 JWK"""
    # 将密钥编码为 base64url
    secret_bytes = secret.encode('utf-8')
    k = base64.urlsafe_b64encode(secret_bytes).decode('utf-8').rstrip('=')
    
    jwk = {
        "kty": "oct",  # 对称密钥
        "alg": "HS256",
        "use": "sig",
        "k": k
    }
    
    return json.dumps(jwk, separators=(',', ':'))


def main():
    """主函数"""
    print("🔑 JWK 生成工具")
    print("=" * 50)
    
    # 从环境变量或用户输入获取密钥
    jwt_secret = os.getenv('JWT_SECRET')
    
    if not jwt_secret:
        print("请输入您的 Supabase JWT Secret:")
        print("(可以在 Supabase Dashboard > Settings > API > JWT Settings 中找到)")
        jwt_secret = input("JWT Secret: ").strip()
    
    if not jwt_secret:
        print("❌ 未提供 JWT Secret")
        return
    
    print(f"🔑 JWT Secret 长度: {len(jwt_secret)}")
    
    # 生成 JWK
    jwk_json = create_hs256_jwk(jwt_secret)
    
    print(f"\n📋 生成的 JWK:")
    print(jwk_json)
    
    print(f"\n💡 请将以下内容添加到 .env 文件:")
    print(f"SUPABASE_JWK={jwk_json}")
    
    # 自动更新 .env 文件
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 替换或添加 SUPABASE_JWK
            lines = content.split('\n')
            updated = False
            
            for i, line in enumerate(lines):
                if line.startswith('SUPABASE_JWK='):
                    lines[i] = f'SUPABASE_JWK={jwk_json}'
                    updated = True
                    break
            
            if not updated:
                # 找到 SUPABASE 配置区域并添加
                for i, line in enumerate(lines):
                    if line.startswith('SUPABASE_PROJECT_ID='):
                        lines.insert(i + 1, f'SUPABASE_JWK={jwk_json}')
                        break
            
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"\n✅ 已自动更新 .env 文件")
            
        except Exception as e:
            print(f"\n⚠️  无法自动更新 .env 文件: {e}")
            print("请手动添加上述配置")


if __name__ == "__main__":
    main()
