#!/usr/bin/env python3
"""检查前后端服务状态"""
import sys
import requests
from pathlib import Path

def check_backend():
    """检查后端服务"""
    print("\n[1] 检查后端服务 (http://localhost:9999)")
    try:
        r = requests.get('http://localhost:9999/api/v1/healthz', timeout=5)
        print(f"  ✅ 后端服务运行正常")
        print(f"  状态码: {r.status_code}")
        print(f"  响应: {r.text[:200]}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 后端服务未运行（连接被拒绝）")
        return False
    except requests.exceptions.Timeout:
        print(f"  ❌ 后端服务响应超时")
        return False
    except Exception as e:
        print(f"  ❌ 后端服务检查失败: {e}")
        return False

def check_frontend():
    """检查前端服务"""
    print("\n[2] 检查前端服务 (http://localhost:3101)")
    try:
        r = requests.get('http://localhost:3101', timeout=5)
        print(f"  ✅ 前端服务运行正常")
        print(f"  状态码: {r.status_code}")
        print(f"  内容长度: {len(r.text)} 字节")
        return True
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 前端服务未运行（连接被拒绝）")
        return False
    except requests.exceptions.Timeout:
        print(f"  ❌ 前端服务响应超时")
        return False
    except Exception as e:
        print(f"  ❌ 前端服务检查失败: {e}")
        return False

def check_database():
    """检查数据库文件"""
    print("\n[3] 检查数据库文件")
    db_path = Path('db.sqlite3')
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"  ✅ 数据库文件存在: {db_path}")
        print(f"  文件大小: {size:,} 字节")
        return True
    else:
        print(f"  ❌ 数据库文件不存在: {db_path}")
        return False

def check_api_docs():
    """检查 API 文档"""
    print("\n[4] 检查 API 文档 (http://localhost:9999/docs)")
    try:
        r = requests.get('http://localhost:9999/docs', timeout=5)
        if r.status_code == 200:
            print(f"  ✅ API 文档可访问")
            print(f"  URL: http://localhost:9999/docs")
            return True
        else:
            print(f"  ⚠️  API 文档返回状态码: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ API 文档检查失败: {e}")
        return False

def main():
    print("=" * 80)
    print("服务状态诊断")
    print("=" * 80)
    
    backend_ok = check_backend()
    frontend_ok = check_frontend()
    db_ok = check_database()
    docs_ok = check_api_docs()
    
    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)
    
    if backend_ok and frontend_ok and db_ok:
        print("✅ 所有服务运行正常")
        print("\n访问地址:")
        print("  前端: http://localhost:3101")
        print("  后端: http://localhost:9999")
        print("  API 文档: http://localhost:9999/docs")
        return 0
    else:
        print("❌ 发现问题:")
        if not backend_ok:
            print("  - 后端服务未运行")
        if not frontend_ok:
            print("  - 前端服务未运行")
        if not db_ok:
            print("  - 数据库文件不存在")
        
        print("\n建议修复步骤:")
        if not db_ok:
            print("  1. 初始化数据库: make migrate && make upgrade")
        if not backend_ok:
            print("  2. 启动后端: python run.py")
        if not frontend_ok:
            print("  3. 启动前端: cd web && pnpm dev")
        
        return 1

if __name__ == '__main__':
    sys.exit(main())

