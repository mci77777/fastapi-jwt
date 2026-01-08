"""E2E: validate reply ThinkingML structure for all mapped models (SSOT).

This test runs the repo script in a subprocess to keep env/SQLite/runtime isolated.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_mapped_models_thinkingml_structure_local_mock_script():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "monitoring" / "local_mock_ai_conversation_e2e.py"
    assert script_path.exists()

    env = os.environ.copy()
    env["SQLITE_DB_PATH"] = "tmp_test/pytest_mapped_models_e2e_db.sqlite3"
    env["AI_RUNTIME_STORAGE_DIR"] = "tmp_test/pytest_mapped_models_e2e_runtime"
    env["SUPABASE_KEEPALIVE_ENABLED"] = "false"
    env["SUPABASE_PROVIDER_ENABLED"] = "false"
    env["ENDPOINT_MONITOR_PROBE_ENABLED"] = "false"
    env["RATE_LIMIT_ENABLED"] = "false"
    env["ALLOW_TEST_AI_ENDPOINTS"] = "true"
    env.setdefault("AI_PROVIDER", "openai")
    env.setdefault("AI_API_KEY", "test-ai-key")
    env.setdefault("AI_MODEL", "mock-model")
    env.setdefault("AI_API_BASE_URL", "https://example.invalid")

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"

