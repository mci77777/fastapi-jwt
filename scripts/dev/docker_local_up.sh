#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/dev/generate_docker_local_env.py

DB_DIR="$ROOT_DIR/db"
DB_PATH="$DB_DIR/db.sqlite3"
# docker bind mount：确保 db 文件存在；并使用目录挂载，避免 WAL/-shm 文件丢失导致状态不落盘
mkdir -p "$DB_DIR"
if [[ -d "$DB_PATH" ]]; then
  echo "Invalid db/db.sqlite3: it's a directory. Remove it and rerun (e.g. rm -rf db/db.sqlite3)."
  exit 2
fi
if [[ ! -e "$DB_PATH" ]]; then
  : >"$DB_PATH"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found. Please enable Docker Desktop WSL integration or install Docker."
  exit 2
fi

docker compose --env-file .env.docker.local -f docker-compose.local.yml up -d --build --force-recreate --remove-orphans
echo "OK. Web: http://localhost:${WEB_PORT:-3101}  API docs: http://localhost:${API_PORT:-9999}/docs"
