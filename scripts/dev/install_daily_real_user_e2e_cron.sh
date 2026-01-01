#!/usr/bin/env bash
set -euo pipefail

# 在 WSL/Linux 上安装一个每日 cron，用于跑「真实用户 JWT → /messages → SSE」闭环。
#
# 注意：
# - 该脚本不会打印任何密钥；E2E 读取 `e2e/anon_jwt_sse/.env.local`（勿入库）。
# - 默认把日志写入 `logs/daily_real_user_e2e.log`。
# - 如需“自动创建用户”，请在 `.env.local` 配置 `SUPABASE_SERVICE_ROLE_KEY`。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab not found. Install cron first (e.g. apt-get install cron) and ensure cron service is running."
  exit 2
fi

mkdir -p logs

JOB_TIME="${JOB_TIME:-15 3 * * *}" # 默认 03:15（与 CI 保持一致，UTC/本地时区以系统为准）
JOB_CMD="cd \"$ROOT_DIR\" && bash scripts/dev/run_local_real_user_e2e.sh >> logs/daily_real_user_e2e.log 2>&1"
JOB_LINE="$JOB_TIME $JOB_CMD"

echo "Install cron job:"
echo "  $JOB_LINE"

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "$EXISTING" | grep -Fq "run_local_real_user_e2e.sh"; then
  echo "Cron already contains run_local_real_user_e2e.sh; no changes made."
  exit 0
fi

{
  echo "$EXISTING"
  [[ -n "$EXISTING" ]] && echo ""
  echo "# GymBro: daily real-user SSE E2E"
  echo "$JOB_LINE"
} | crontab -

echo "OK. Verify with: crontab -l | grep run_local_real_user_e2e.sh"

