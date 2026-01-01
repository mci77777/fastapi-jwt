import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_REAL_USER_E2E") not in ("1", "true", "TRUE", "yes", "YES"),
    reason="需要显式启用：RUN_REAL_USER_E2E=1，并提供 Supabase/ServiceRole/API env（真实用户注册→登录→对话）",
)
def test_real_user_signup_login_sse_e2e_script():
    script = os.path.join("scripts", "monitoring", "real_user_signup_login_sse_e2e.py")
    proc = subprocess.run([sys.executable, script], check=False)  # noqa: S603,S607
    assert proc.returncode == 0

