#!/usr/bin/env python3
"""检查数据库表和用户数据"""
import sys
import sqlite3
from pathlib import Path

def check_tables():
    """检查数据库表"""
    db_path = Path('db.sqlite3')
    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return False
    
    print("\n[1] 检查数据库表")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        print(f"  ✅ 找到 {len(tables)} 个表:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"    - {table_name}: {count} 条记录")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ 检查表失败: {e}")
        return False

def check_users():
    """检查用户表"""
    db_path = Path('db.sqlite3')
    if not db_path.exists():
        return False
    
    print("\n[2] 检查用户数据")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 检查是否有 user 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%'")
        user_tables = cursor.fetchall()
        
        if not user_tables:
            print("  ⚠️  未找到用户表")
            print("  提示: 此项目可能使用 Supabase 作为用户认证系统")
            conn.close()
            return True
        
        print(f"  找到用户相关表: {[t[0] for t in user_tables]}")
        
        for table in user_tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"    - {table_name}: {count} 个用户")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ 检查用户失败: {e}")
        return False

def check_auth_config():
    """检查认证配置"""
    print("\n[3] 检查认证配置")
    
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_issuer = os.getenv('SUPABASE_ISSUER')
    
    if supabase_url:
        print(f"  ✅ 使用 Supabase 认证")
        print(f"    URL: {supabase_url}")
        print(f"    Issuer: {supabase_issuer}")
        print(f"\n  💡 提示: 需要通过 Supabase Auth 登录才能获取 JWT token")
        return True
    else:
        print(f"  ⚠️  未配置 Supabase")
        return False

def main():
    print("=" * 80)
    print("数据库诊断")
    print("=" * 80)
    
    tables_ok = check_tables()
    users_ok = check_users()
    auth_ok = check_auth_config()
    
    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)
    
    if tables_ok and auth_ok:
        print("✅ 数据库配置正常")
        print("\n关于 localStorage 中没有 ACCESS_TOKEN 的问题:")
        print("  原因: 您还没有登录")
        print("  解决: 访问前端应用并完成登录流程")
        print("\n登录步骤:")
        print("  1. 打开浏览器访问: http://localhost:3101")
        print("  2. 如果有登录页面，使用 Supabase 账号登录")
        print("  3. 登录成功后，ACCESS_TOKEN 会自动保存到 localStorage")
        print("  4. 然后可以使用测试工具进行 WebSocket 测试")
        return 0
    else:
        print("❌ 发现问题")
        if not tables_ok:
            print("  - 数据库表检查失败")
        if not auth_ok:
            print("  - 认证配置检查失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())

