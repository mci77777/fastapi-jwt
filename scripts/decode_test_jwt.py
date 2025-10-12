"""解码测试 JWT token。"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import jwt

# 生成 token
result = subprocess.run(
    ["python", "scripts/create_test_jwt.py"],
    capture_output=True,
    text=True,
    check=True,
)
token = result.stdout.strip()

# 解码 token（不验证签名）
decoded = jwt.decode(token, options={"verify_signature": False})

print("JWT Payload:")
for key, value in decoded.items():
    print(f"  {key}: {value}")

