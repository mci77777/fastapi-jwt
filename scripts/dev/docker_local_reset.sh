#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# 目标：本地 Docker “完整重建”，用于修复：
# - dashboard 无法登录（db/local_users 状态漂移）
# - 端口/静态产物未更新（旧镜像缓存）
# - sqlite 挂载异常
#
# 默认会删除宿主 db/db.sqlite3（恢复到 admin/123456 的干净状态）。
# 如需保留数据库：KEEP_DB=1 bash scripts/dev/docker_local_reset.sh

KEEP_DB="${KEEP_DB:-0}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found. Please enable Docker Desktop WSL integration or install Docker."
  exit 2
fi

# 先生成 env，确保 compose 文件路径/端口 SSOT 一致
python3 scripts/dev/generate_docker_local_env.py

docker compose --env-file .env.docker.local -f docker-compose.local.yml down --remove-orphans || true

if [[ "$KEEP_DB" != "1" ]]; then
  rm -f "$ROOT_DIR/db/db.sqlite3" "$ROOT_DIR/db/db.sqlite3-wal" "$ROOT_DIR/db/db.sqlite3-shm"
fi

# 强制重建镜像（避免静态产物/环境变量缓存）
docker image rm -f vue-fastapi-admin:local >/dev/null 2>&1 || true

bash scripts/dev/docker_local_up.sh
