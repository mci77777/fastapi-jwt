import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_REAL_USER_E2E") not in ("1", "true", "TRUE", "yes", "YES"),
    reason="需要显式启用：RUN_REAL_USER_E2E=1，并提供 E2E_* 环境变量（真实用户，不做 mock）",
)
def test_real_user_sse_e2e_script():
    """
    真实用户 E2E（外网 + 真实 Supabase + 本地后端端口）。

    说明：
    - 默认跳过，避免在无真实凭证/无后端服务时误失败
    - 使用脚本做闭环：Supabase 登录 → /messages → SSE
    """
    script = os.path.join("scripts", "monitoring", "real_user_sse_e2e.py")
    proc = subprocess.run([sys.executable, script], check=False)  # noqa: S603,S607
    assert proc.returncode == 0
