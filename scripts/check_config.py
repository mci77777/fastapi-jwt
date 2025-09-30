#!/usr/bin/env python3
"""
简单的配置检查脚本
检查 .env 文件中的 Supabase 配置是否完整
"""

import os
from pathlib import Path


def check_env_file():
    """检查 .env 文件配置"""
    env_path = Path(__file__).parent.parent / '.env'

    if not env_path.exists():
        print("[ERROR] .env 文件不存在")
        return False

    print(f"[INFO] 检查配置文件: {env_path}")

    # 读取 .env 文件
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    # 检查必需的配置项
    required_vars = [
        'SUPABASE_PROJECT_ID',
        'SUPABASE_JWKS_URL',
        'SUPABASE_ISSUER',
        'SUPABASE_AUDIENCE',
        'SUPABASE_SERVICE_ROLE_KEY',
        'AI_PROVIDER',
        'AI_MODEL',
        'AI_API_KEY'
    ]

    all_configured = True

    print("\n配置检查结果:")
    print("-" * 50)

    for var in required_vars:
        if var not in env_vars:
            print(f"[ERROR] ❌ {var}: 未设置")
            all_configured = False
        elif not env_vars[var] or env_vars[var].startswith('your-'):
            print(f"[ERROR] ❌ {var}: 使用默认占位符，需要替换为实际值")
            all_configured = False
        else:
            # 隐藏敏感信息
            if 'KEY' in var or 'SECRET' in var:
                display_value = env_vars[var][:8] + "..." if len(env_vars[var]) > 8 else "***"
            else:
                display_value = env_vars[var]
            print(f"[SUCCESS] ✅ {var}: {display_value}")

    print("-" * 50)

    if all_configured:
        print("[SUCCESS] 🎉 所有必需配置项都已设置！")
        print("\n下一步:")
        print("1. 确保 Supabase 项目已创建")
        print("2. 运行 SQL 脚本创建数据库表: docs/jwt改造/supabase_schema.sql")
        print("3. 启动服务: python run.py")
        return True
    else:
        print("[ERROR] ❌ 部分配置项缺失或未正确设置")
        print("\n修复步骤:")
        print("1. 参考 docs/jwt改造/SUPABASE_SETUP_GUIDE.md 创建 Supabase 项目")
        print("2. 将获取的配置信息替换 .env 文件中的占位符")
        print("3. 重新运行此脚本验证配置")
        return False


def main():
    """主函数"""
    print("GymBro API 配置检查工具")
    print("=" * 50)

    success = check_env_file()

    print("\n" + "=" * 50)

    if success:
        print("配置检查完成 - 所有配置正确 ✅")
        return 0
    else:
        print("配置检查完成 - 需要修复配置 ❌")
        return 1


if __name__ == '__main__':
    exit(main())
