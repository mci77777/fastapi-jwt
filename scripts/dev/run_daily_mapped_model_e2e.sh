#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

E2E_ENV_FILE="${E2E_ENV_PATH:-e2e/anon_jwt_sse/.env.local}"
ROOT_ENV_FILE="${ROOT_ENV_PATH:-$ROOT_DIR/.env}"

if [[ ! -f "$E2E_ENV_FILE" ]]; then
  echo "Missing env file: $E2E_ENV_FILE"
  exit 2
fi

if command -v flock >/dev/null 2>&1; then
  LOCK_FILE="${E2E_LOCK_FILE:-/tmp/gymbro_daily_mapped_model_e2e.lock}"
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "Daily E2E already running; skip."
    exit 0
  fi
fi

# Load root .env (if present), then override with e2e/.env.local
if [[ -f "$ROOT_ENV_FILE" ]]; then
  while IFS= read -r raw_line || [[ -n "${raw_line:-}" ]]; do
    line="${raw_line%$'\r'}"
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      key="${line%%=*}"
      val="${line#*=}"
      if [[ "$val" =~ ^\".*\"$ ]]; then val="${val:1:${#val}-2}"; fi
      if [[ "$val" =~ ^\'.*\'$ ]]; then val="${val:1:${#val}-2}"; fi
      export "$key=$val"
    fi
  done <"$ROOT_ENV_FILE"
fi

while IFS= read -r raw_line || [[ -n "${raw_line:-}" ]]; do
  line="${raw_line%$'\r'}"
  [[ -z "$line" ]] && continue
  [[ "$line" == \#* ]] && continue
  if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
    key="${line%%=*}"
    val="${line#*=}"
    if [[ "$val" =~ ^\".*\"$ ]]; then val="${val:1:${#val}-2}"; fi
    if [[ "$val" =~ ^\'.*\'$ ]]; then val="${val:1:${#val}-2}"; fi
    export "$key=$val"
  fi
done <"$E2E_ENV_FILE"

API_BASE_LOCAL="${E2E_API_BASE_LOCAL:-http://127.0.0.1:${API_PORT:-9999}/api/v1}"
export E2E_API_BASE="$API_BASE_LOCAL"

export E2E_USE_DASHBOARD_CONFIG="${E2E_USE_DASHBOARD_CONFIG:-1}"
export E2E_RESULT_MODE="${E2E_RESULT_MODE:-xml_plaintext}"
export E2E_VALIDATE_THINKINGML="${E2E_VALIDATE_THINKINGML:-1}"

echo "E2E env: $E2E_ENV_FILE (keys loaded; values not printed)"
echo "Root env: $(basename "$ROOT_ENV_FILE") (keys loaded; values not printed)"
echo "E2E target: $E2E_API_BASE"

if [[ "${E2E_SCHEDULE_CHECK:-}" == "1" ]]; then
  if ! python3 scripts/monitoring/daily_mapped_model_schedule_check.py; then
    echo "Daily E2E skipped (not scheduled time or already ran today)."
    exit 0
  fi
fi

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

if ! "$PY" -c "import aiohttp" >/dev/null 2>&1; then
  echo "Install dep in venv: aiohttp"
  "$PY" -m pip install --quiet aiohttp
fi

if ! "$PY" -c "import aiosqlite" >/dev/null 2>&1; then
  echo "Install dep in venv: aiosqlite"
  "$PY" -m pip install --quiet aiosqlite
fi

if ! "$PY" -c "import dotenv" >/dev/null 2>&1; then
  echo "Install dep in venv: python-dotenv"
  "$PY" -m pip install --quiet python-dotenv
fi

PYTHONPATH="$ROOT_DIR" "$PY" scripts/monitoring/daily_mapped_model_jwt_e2e.py
