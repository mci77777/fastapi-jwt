#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/dev/generate_docker_local_env.py

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found. Please enable Docker Desktop WSL integration or install Docker."
  exit 2
fi

docker compose --env-file .env.docker.local -f docker-compose.local.yml up -d --build
echo "OK. Web: http://localhost:${WEB_PORT:-3101}  API docs: http://localhost:${API_PORT:-9999}/docs"
