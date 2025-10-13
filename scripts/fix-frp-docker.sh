#!/bin/bash
# FRP Docker Fix Script
# Purpose: Fix FRP Docker configuration and restart container
# Author: GymBro Team
# Date: 2025-01-13

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

log_info() { echo -e "${CYAN}$1${NC}"; }
log_success() { echo -e "${GREEN}$1${NC}"; }
log_warn() { echo -e "${YELLOW}$1${NC}"; }
log_error() { echo -e "${RED}$1${NC}"; }
log_gray() { echo -e "${GRAY}$1${NC}"; }

# Configuration
ENV_FILE="$(dirname "$0")/../.env"
FRP_CONFIG_DIR="$(dirname "$0")/../frp"
FRP_CONFIG_FILE="${FRP_CONFIG_DIR}/frpc.toml"

# Read .env
FRP_BASE_IP=$(grep "^FRP_BASE_IP=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
FRP_TOKEN=$(grep "^FRP_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

log_info "\n========================================"
log_info " FRP Docker Fix Script"
log_info "========================================\n"

# Step 1: Detect host IP
log_info "[1/5] Detecting host IP for Docker..."

# Try multiple methods to get host IP
HOST_IP=""

# Method 1: WSL gateway IP
if grep -qi microsoft /proc/version 2>/dev/null; then
    HOST_IP=$(ip route | grep default | awk '{print $3}')
    log_gray "  WSL detected, gateway IP: $HOST_IP"
fi

# Method 2: Docker bridge gateway
if [ -z "$HOST_IP" ]; then
    HOST_IP="172.17.0.1"
    log_gray "  Using Docker bridge gateway: $HOST_IP"
fi

# Method 3: Test connectivity
log_gray "  Testing connectivity to host services..."
if nc -z $HOST_IP 9999 2>/dev/null; then
    log_success "  [OK] Can reach host port 9999 from $HOST_IP"
else
    log_warn "  [WARN] Cannot reach host port 9999 from $HOST_IP"
    log_gray "  Trying alternative: host.docker.internal"
    HOST_IP="host.docker.internal"
fi

log_success "  [OK] Using host IP: $HOST_IP"

# Step 2: Generate new configuration
log_info "\n[2/5] Generating new FRP configuration..."

mkdir -p "$FRP_CONFIG_DIR"

cat > "$FRP_CONFIG_FILE" <<EOF
# FRP Client Configuration
# Auto-generated at $(date '+%Y-%m-%d %H:%M:%S')
# Fixed for Docker container

serverAddr = "$FRP_BASE_IP"
serverPort = 7000

auth.method = "token"
auth.token = "$FRP_TOKEN"

log.level = "info"
log.maxDays = 3

# Backend API service (FastAPI on port 9999)
[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "$HOST_IP"
localPort = 9999
remotePort = 9999

# Frontend service (Vue3 on port 3101)
[[proxies]]
name = "gymbro-frontend"
type = "tcp"
localIP = "$HOST_IP"
localPort = 3101
remotePort = 3101

# HTTP proxy for API domain
[[proxies]]
name = "gymbro-api-http"
type = "http"
localIP = "$HOST_IP"
localPort = 9999
customDomains = ["api.gymbro.cloud"]

# HTTP proxy for Web domain
[[proxies]]
name = "gymbro-web-http"
type = "http"
localIP = "$HOST_IP"
localPort = 3101
customDomains = ["web.gymbro.cloud"]
EOF

log_success "  [OK] Configuration file generated"
log_gray "  Config file: $FRP_CONFIG_FILE"
log_gray "  Host IP: $HOST_IP"

# Step 3: Stop existing container
log_info "\n[3/5] Stopping existing FRP container..."

EXISTING_CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep -E '^frpc' || true)
if [ -n "$EXISTING_CONTAINERS" ]; then
    log_gray "  Found containers: $EXISTING_CONTAINERS"
    for container in $EXISTING_CONTAINERS; do
        log_gray "  Stopping $container..."
        docker stop "$container" 2>/dev/null || true
        docker rm "$container" 2>/dev/null || true
    done
    log_success "  [OK] Existing containers removed"
else
    log_gray "  No existing containers found"
fi

# Step 4: Start new container
log_info "\n[4/5] Starting new FRP container..."

CONTAINER_NAME="frpc-gymbro"
# Use official FRP image that supports TOML format
IMAGE_NAME="fatedier/frpc:v0.61.1"

log_gray "  Pulling image: $IMAGE_NAME"
docker pull "$IMAGE_NAME" 2>&1 | grep -E "(Pulling|Downloaded|Status)" || true

log_gray "  Starting container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --add-host=host.docker.internal:host-gateway \
    --network host \
    -v "$(realpath "$FRP_CONFIG_FILE"):/etc/frp/frpc.toml:ro" \
    "$IMAGE_NAME" \
    -c /etc/frp/frpc.toml

sleep 5

# Step 5: Verify
log_info "\n[5/5] Verifying container status..."

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    CONTAINER_ID=$(docker ps -q -f name="^${CONTAINER_NAME}$")
    log_success "  [OK] Container started (ID: ${CONTAINER_ID:0:12})"
    
    log_gray "\n  Checking logs..."
    docker logs --tail 20 "$CONTAINER_NAME" 2>&1 | tail -10
    
    log_info "\n========================================"
    log_info " FRP Container Information"
    log_info "========================================\n"
    
    log_gray "Container name: $CONTAINER_NAME"
    log_gray "Host IP: $HOST_IP"
    log_gray "Config file: $FRP_CONFIG_FILE"
    
    log_info "\nManagement Commands:"
    log_gray "  View logs:    docker logs -f $CONTAINER_NAME"
    log_gray "  Stop service: docker stop $CONTAINER_NAME"
    log_gray "  Restart:      docker restart $CONTAINER_NAME"
    log_gray "  Remove:       docker rm -f $CONTAINER_NAME"
    
    log_info "\nRemote Access:"
    log_gray "  Frontend: http://${FRP_BASE_IP}:3101"
    log_gray "  Backend:  http://${FRP_BASE_IP}:9999"
    log_gray "  API Domain: http://api.gymbro.cloud"
    
    log_info "\n========================================\n"
    log_success "FRP container fixed and restarted successfully!"
else
    log_error "  [ERROR] Container failed to start"
    log_gray "  Check logs: docker logs $CONTAINER_NAME"
    exit 1
fi

