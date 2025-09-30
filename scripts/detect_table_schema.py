#!/usr/bin/env python3
"""检测实际的表结构。"""

import json
from pathlib import Path
from typing import Dict, List

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


def test_table_exists(client: httpx.Client, supabase_url: str, service_role_key: str, table_name: str) -> bool:
    """测试表是否存在。"""
    try:
        response = client.get(
            f"{supabase_url}/rest/v1/{table_name}",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json"
            },
            params={"limit": "0"}  # 只检查表是否存在，不返回数据
        )
        return response.status_code == 200
    except:
        return False


def detect_column_names(client: httpx.Client, supabase_url: str, service_role_key: str, table_name: str) -> List[str]:
    """通过尝试不同的列名来检测表结构。"""
    possible_time_columns = ["timestamp", "created_at", "createdAt", "created", "time"]
    existing_columns = []
    
    for col in possible_time_columns:
        try:
            response = client.get(
                f"{supabase_url}/rest/v1/{table_name}",
                headers={
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": "1", "order": f"{col}.desc"}
            )
            if response.status_code == 200:
                existing_columns.append(col)
                print(f"   ✅ 列 '{col}' 存在")
            else:
                print(f"   ❌ 列 '{col}' 不存在: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 测试列 '{col}' 时出错: {e}")
    
    return existing_columns


def main():
    """主函数。"""
    print("🔍 检测数据库表结构")
    print("=" * 50)
    
    env_vars = load_env_file()
    supabase_url = env_vars.get("SUPABASE_URL")
    service_role_key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
    configured_table = env_vars.get("SUPABASE_CHAT_TABLE", "ai_chat_messages")
    
    if not supabase_url or not service_role_key:
        print("❌ Supabase 配置不完整")
        return 1
    
    print(f"🔗 Supabase URL: {supabase_url}")
    print(f"📋 配置的表名: {configured_table}")
    
    # 测试可能的表名
    possible_tables = ["ai_chat_messages", "chat_messages", "messages"]
    
    try:
        with httpx.Client(timeout=15.0) as client:
            print(f"\n🔍 测试表是否存在...")
            
            existing_tables = []
            for table in possible_tables:
                if test_table_exists(client, supabase_url, service_role_key, table):
                    existing_tables.append(table)
                    print(f"   ✅ 表 '{table}' 存在")
                else:
                    print(f"   ❌ 表 '{table}' 不存在")
            
            if not existing_tables:
                print(f"\n❌ 没有找到任何聊天消息表")
                return 1
            
            print(f"\n📊 找到 {len(existing_tables)} 个表: {existing_tables}")
            
            # 对每个存在的表检测列结构
            for table in existing_tables:
                print(f"\n🔍 检测表 '{table}' 的列结构:")
                columns = detect_column_names(client, supabase_url, service_role_key, table)
                
                if columns:
                    print(f"   📋 时间相关列: {columns}")
                    
                    # 尝试查询一条记录来了解完整结构
                    try:
                        response = client.get(
                            f"{supabase_url}/rest/v1/{table}",
                            headers={
                                "apikey": service_role_key,
                                "Authorization": f"Bearer {service_role_key}",
                                "Content-Type": "application/json"
                            },
                            params={"limit": "1"}
                        )
                        
                        if response.status_code == 200:
                            records = response.json()
                            if records:
                                print(f"   📋 完整列结构:")
                                for key in records[0].keys():
                                    print(f"      - {key}")
                            else:
                                print(f"   ⚠️  表为空，无法获取完整结构")
                        else:
                            print(f"   ❌ 查询失败: {response.status_code}")
                            
                    except Exception as e:
                        print(f"   ❌ 查询表结构时出错: {e}")
                else:
                    print(f"   ⚠️  未找到时间相关列")
            
            # 给出建议
            print(f"\n💡 建议:")
            if configured_table in existing_tables:
                print(f"   ✅ 配置的表 '{configured_table}' 存在，建议使用它")
            else:
                if existing_tables:
                    recommended = existing_tables[0]
                    print(f"   ⚠️  配置的表 '{configured_table}' 不存在")
                    print(f"   💡 建议更新 .env 中的 SUPABASE_CHAT_TABLE 为: {recommended}")
                else:
                    print(f"   ❌ 需要先创建聊天消息表")
            
            return 0
            
    except Exception as e:
        print(f"❌ 操作异常: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
