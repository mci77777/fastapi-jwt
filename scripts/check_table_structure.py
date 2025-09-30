#!/usr/bin/env python3
"""检查数据库表结构。"""

import json
from pathlib import Path
from typing import Dict

try:
    import httpx
except ImportError:
    print("❌ 需要安装依赖: pip install httpx")
    exit(1)


def load_env_file() -> Dict[str, str]:
    """加载 .env 文件。"""
    env_file = Path(__file__).parent.parent / ".env"
    env_vars = {}
    
    if not env_file.exists():
        print(f"❌ .env 文件不存在: {env_file}")
        return env_vars
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def check_table_structure():
    """检查表结构。"""
    print("🔍 检查数据库表结构")
    print("=" * 50)
    
    env_vars = load_env_file()
    supabase_url = env_vars.get("SUPABASE_URL")
    service_role_key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
    chat_table = env_vars.get("SUPABASE_CHAT_TABLE", "ai_chat_messages")
    
    if not supabase_url or not service_role_key:
        print("❌ Supabase 配置不完整")
        return False
    
    print(f"📋 表名: {chat_table}")
    print(f"🔗 Supabase URL: {supabase_url}")
    
    try:
        with httpx.Client(timeout=15.0) as client:
            # 1. 尝试查询表结构（通过查询一条记录来了解列名）
            table_url = f"{supabase_url}/rest/v1/{chat_table}"
            
            print(f"\n🔍 查询表结构...")
            response = client.get(
                table_url,
                headers={
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "1"}
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                records = response.json()
                print(f"✅ 表查询成功")
                print(f"📊 记录数: {len(records)}")
                
                if records:
                    print(f"\n📋 表结构（基于第一条记录）:")
                    first_record = records[0]
                    for key, value in first_record.items():
                        value_type = type(value).__name__
                        value_preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                        print(f"   {key}: {value_type} = {value_preview}")
                else:
                    print(f"⚠️  表为空，无法确定结构")
                    
                    # 尝试插入一条测试记录来了解必需字段
                    print(f"\n🧪 尝试插入测试记录来了解表结构...")
                    test_record = {
                        "id": "test-structure-check",
                        "conversation_id": "test-conv",
                        "role": "user",
                        "content": "test message",
                        "created_at": "2025-09-29T13:00:00Z"
                    }
                    
                    insert_response = client.post(
                        table_url,
                        headers={
                            "apikey": service_role_key,
                            "Authorization": f"Bearer {service_role_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal"
                        },
                        json=test_record
                    )
                    
                    print(f"插入测试状态码: {insert_response.status_code}")
                    if insert_response.status_code in [200, 201]:
                        print(f"✅ 测试记录插入成功")
                        
                        # 删除测试记录
                        delete_response = client.delete(
                            f"{table_url}?id=eq.test-structure-check",
                            headers={
                                "apikey": service_role_key,
                                "Authorization": f"Bearer {service_role_key}",
                            }
                        )
                        print(f"删除测试记录状态码: {delete_response.status_code}")
                    else:
                        print(f"❌ 测试记录插入失败: {insert_response.text}")
                        print(f"这可以帮助我们了解表的约束和必需字段")
                
                return True
            else:
                print(f"❌ 表查询失败: {response.status_code}")
                print(f"响应: {response.text}")
                
                # 检查是否是表不存在
                if response.status_code == 404:
                    print(f"\n💡 可能的原因:")
                    print(f"   1. 表 '{chat_table}' 不存在")
                    print(f"   2. 表名配置错误")
                    print(f"   3. RLS 策略阻止了访问")
                
                return False
                
    except Exception as e:
        print(f"❌ 操作异常: {e}")
        return False


def main():
    """主函数。"""
    print("🚀 数据库表结构检查工具\n")
    
    success = check_table_structure()
    
    if success:
        print(f"\n🎉 表结构检查完成!")
        return 0
    else:
        print(f"\n❌ 表结构检查失败")
        return 1


if __name__ == "__main__":
    exit(main())
