#!/usr/bin/env python3
"""快速测试 JWT 验证（支持从剪贴板读取）"""
import sys, os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def main():
    # 尝试从剪贴板读取
    token = None
    try:
        import pyperclip
        clipboard = pyperclip.paste()
        if clipboard and clipboard.startswith('eyJ'):
            token = clipboard.strip()
            print(f"📋 从剪贴板读取到 token (长度: {len(token)})")
    except ImportError:
        pass
    
    # 从命令行参数读取
    if not token and len(sys.argv) > 1:
        token = sys.argv[1]
    
    # 从环境变量读取
    if not token:
        token = os.getenv('TEST_JWT_TOKEN')
    
    if not token:
        print("❌ 未找到 JWT token")
        print("\n使用方法（任选其一）:")
        print("  1. 复制 token 到剪贴板后运行: python scripts/quick_test_jwt.py")
        print("  2. 命令行参数: python scripts/quick_test_jwt.py <token>")
        print("  3. 环境变量: TEST_JWT_TOKEN=<token> python scripts/quick_test_jwt.py")
        return 1
    
    # 调用完整的验证脚本
    import subprocess
    result = subprocess.run(
        [sys.executable, str(project_root / 'scripts' / 'tmp_verify_es256_jwt.py'), token],
        cwd=str(project_root)
    )
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())

