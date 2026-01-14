#!/usr/bin/env bash
set -euo pipefail

# Install cron: mapped-model JWT E2E (message-only, schedule from Dashboard config).
#
# Notes:
# - Reads env from `.env` + `e2e/anon_jwt_sse/.env.local`.
# - Writes logs to `logs/daily_mapped_model_e2e.log`.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab not found. Install cron first (e.g. apt-get install cron) and ensure cron service is running."
  exit 2
fi

mkdir -p logs

# Run schedule gate every minute; actual run time is decided by dashboard_config.e2e_daily_time.
JOB_TIME="${JOB_TIME:-* * * * *}"
JOB_CMD="cd \"$ROOT_DIR\" && E2E_SCHEDULE_CHECK=1 E2E_USE_DASHBOARD_CONFIG=1 bash scripts/dev/run_daily_mapped_model_e2e.sh >> logs/daily_mapped_model_e2e.log 2>&1"
JOB_LINE="$JOB_TIME $JOB_CMD"

echo "Install cron job:"
echo "  $JOB_LINE"

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(echo "$EXISTING" | grep -v \"run_daily_mapped_model_e2e.sh\" || true)"

{
  echo "$FILTERED"
  [[ -n "$FILTERED" ]] && echo ""
  echo "# GymBro: daily mapped-model JWT E2E"
  echo "$JOB_LINE"
} | crontab -

echo "OK. Verify with: crontab -l | grep run_daily_mapped_model_e2e.sh"
