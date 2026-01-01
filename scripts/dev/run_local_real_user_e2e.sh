#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

E2E_ENV_FILE="${E2E_ENV_PATH:-e2e/anon_jwt_sse/.env.local}"

if [[ ! -f "$E2E_ENV_FILE" ]]; then
  echo "Missing env file: $E2E_ENV_FILE"
  exit 2
fi

while IFS= read -r raw_line || [[ -n "${raw_line:-}" ]]; do
  line="${raw_line%$'\r'}"
  [[ -z "$line" ]] && continue
  [[ "$line" == \#* ]] && continue
  if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
    key="${line%%=*}"
    val="${line#*=}"
    # 去掉可能的引号
    if [[ "$val" =~ ^\".*\"$ ]]; then val="${val:1:${#val}-2}"; fi
    if [[ "$val" =~ ^\'.*\'$ ]]; then val="${val:1:${#val}-2}"; fi
    export "$key=$val"
  fi
done <"$E2E_ENV_FILE"

API_BASE_LOCAL="${E2E_API_BASE_LOCAL:-http://127.0.0.1:${API_PORT:-9999}/api/v1}"
export E2E_API_BASE="$API_BASE_LOCAL"

echo "E2E env: $E2E_ENV_FILE (keys loaded; values not printed)"
echo "E2E target: $E2E_API_BASE"

VENV_DIR="${E2E_VENV_DIR:-.venv-e2e}"
PY="$VENV_DIR/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Create venv: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

if ! "$PY" -c "import httpx" >/dev/null 2>&1; then
  echo "Install dep in venv: httpx"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet httpx
fi

# 优先跑“创建真实用户”的每日脚本（需要 service role key）
if [[ -n "${E2E_SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}" ]]; then
  export E2E_SUPABASE_URL="${E2E_SUPABASE_URL:-${SUPABASE_URL:-}}"
  export E2E_SUPABASE_ANON_KEY="${E2E_SUPABASE_ANON_KEY:-${SUPABASE_ANON_KEY:-}}"
  export E2E_SUPABASE_SERVICE_ROLE_KEY="${E2E_SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"
echo "Run: scripts/monitoring/real_user_signup_login_sse_e2e.py"
  PYTHONPATH="$ROOT_DIR" "$PY" scripts/monitoring/real_user_signup_login_sse_e2e.py
  exit $?
fi

echo "Run: scripts/monitoring/real_user_sse_e2e.py (reuse TEST_USER_EMAIL/TEST_USER_PASSWORD)"
PYTHONPATH="$ROOT_DIR" "$PY" scripts/monitoring/real_user_sse_e2e.py
