#!/bin/bash
# FRP Client Docker Auto-Start Script
# Purpose: Run FRP client in Docker container (WSL Debian)
# Author: GymBro Team
# Date: 2025-01-13

set -e

# Configuration
FRP_VERSION="0.61.1"
CONTAINER_NAME="frpc-gymbro"
IMAGE_NAME="snowdreamtech/frpc:${FRP_VERSION}"
ENV_FILE="$(dirname "$0")/../.env"
FRP_CONFIG_DIR="$(dirname "$0")/../frp"
FRP_CONFIG_FILE="${FRP_CONFIG_DIR}/frpc.toml"

# Local service ports
FRONTEND_PORT=3101
BACKEND_PORT=9999

# Remote mapping ports
REMOTE_FRONTEND_PORT=3101
REMOTE_BACKEND_PORT=9999

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Helper Functions
log_info() {
    echo -e "${CYAN}$1${NC}"
}

log_success() {
    echo -e "${GREEN}$1${NC}"
}

log_warn() {
    echo -e "${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${RED}$1${NC}"
}

log_gray() {
    echo -e "${GRAY}$1${NC}"
}

read_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "ERROR: .env file not found: $ENV_FILE"
        exit 1
    fi
    
    # Read FRP configuration from .env
    FRP_BASE_IP=$(grep "^FRP_BASE_IP=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    FRP_TOKEN=$(grep "^FRP_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    
    if [ -z "$FRP_BASE_IP" ] || [ -z "$FRP_TOKEN" ]; then
        log_error "ERROR: Missing FRP_BASE_IP or FRP_TOKEN in .env"
        exit 1
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "ERROR: Docker is not installed"
        log_gray "  Install Docker: https://docs.docker.com/engine/install/debian/"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        log_error "ERROR: Docker daemon is not running"
        log_gray "  Start Docker: sudo systemctl start docker"
        exit 1
    fi
}

generate_frp_config() {
    log_info "\n[1/5] Generating FRP configuration..."

    mkdir -p "$FRP_CONFIG_DIR"

    log_gray "  Server address: $FRP_BASE_IP"
    log_gray "  Auth token: ${FRP_TOKEN:0:8}..."

    # Detect host IP for Docker container to access host services
    # In WSL, use host.docker.internal or gateway IP
    HOST_IP="172.17.0.1"  # Default Docker bridge gateway
    if grep -qi microsoft /proc/version 2>/dev/null; then
        # WSL environment - use Windows host IP
        HOST_IP=$(ip route | grep default | awk '{print $3}')
        log_gray "  WSL detected, using host IP: $HOST_IP"
    fi

    cat > "$FRP_CONFIG_FILE" <<EOF
# FRP Client Configuration
# Auto-generated at $(date '+%Y-%m-%d %H:%M:%S')

# Server configuration
serverAddr = "$FRP_BASE_IP"
serverPort = 7000

# Authentication
auth.method = "token"
auth.token = "$FRP_TOKEN"

# Logging
log.level = "info"
log.maxDays = 3

# Backend service tunnel (FastAPI server)
[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "$HOST_IP"
localPort = $BACKEND_PORT
remotePort = $REMOTE_BACKEND_PORT

# Frontend service tunnel (Vue3 dev server)
[[proxies]]
name = "gymbro-frontend"
type = "tcp"
localIP = "$HOST_IP"
localPort = $FRONTEND_PORT
remotePort = $REMOTE_FRONTEND_PORT

# HTTP proxy for API domain access
[[proxies]]
name = "gymbro-api-http"
type = "http"
localIP = "$HOST_IP"
localPort = $BACKEND_PORT
customDomains = ["api.gymbro.cloud"]

# HTTP proxy for Web domain access
[[proxies]]
name = "gymbro-web-http"
type = "http"
localIP = "$HOST_IP"
localPort = $FRONTEND_PORT
customDomains = ["web.gymbro.cloud"]
EOF

    log_success "  [OK] Configuration file generated: $FRP_CONFIG_FILE"
    log_gray "  Host IP for Docker: $HOST_IP"
}

check_local_services() {
    log_info "\n[2/5] Checking local services..."
    
    frontend_running=false
    backend_running=false
    
    if nc -z localhost $FRONTEND_PORT 2>/dev/null; then
        log_success "  [OK] Frontend service running (port $FRONTEND_PORT)"
        frontend_running=true
    else
        log_warn "  [WARN] Frontend service not running (port $FRONTEND_PORT)"
    fi
    
    if nc -z localhost $BACKEND_PORT 2>/dev/null; then
        log_success "  [OK] Backend service running (port $BACKEND_PORT)"
        backend_running=true
    else
        log_warn "  [WARN] Backend service not running (port $BACKEND_PORT)"
    fi
    
    if [ "$frontend_running" = false ] && [ "$backend_running" = false ]; then
        log_warn "\n  [WARN] No local services running"
        log_gray "  Suggestion: Start services first"
        read -p "  Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warn "\n  Cancelled"
            exit 0
        fi
    fi
}

pull_docker_image() {
    log_info "\n[3/5] Pulling Docker image..."
    
    if docker image inspect "$IMAGE_NAME" &> /dev/null; then
        log_success "  [OK] Docker image already exists: $IMAGE_NAME"
    else
        log_gray "  Pulling image: $IMAGE_NAME"
        docker pull "$IMAGE_NAME"
        log_success "  [OK] Docker image pulled successfully"
    fi
}

stop_existing_container() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "  [WARN] Existing container detected: $CONTAINER_NAME"
        read -p "  Stop and remove existing container? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker stop "$CONTAINER_NAME" 2>/dev/null || true
            docker rm "$CONTAINER_NAME" 2>/dev/null || true
            log_success "  [OK] Existing container removed"
        else
            log_warn "  Cancelled"
            exit 0
        fi
    fi
}

start_frp_container() {
    log_info "\n[4/5] Starting FRP container..."
    
    stop_existing_container
    
    log_gray "  Container name: $CONTAINER_NAME"
    log_gray "  Image: $IMAGE_NAME"
    log_gray "  Config file: $FRP_CONFIG_FILE"
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        --network host \
        -v "$(realpath "$FRP_CONFIG_FILE"):/etc/frp/frpc.toml:ro" \
        "$IMAGE_NAME"
    
    sleep 3
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        CONTAINER_ID=$(docker ps -q -f name="^${CONTAINER_NAME}$")
        log_success "  [OK] FRP container started (ID: ${CONTAINER_ID:0:12})"
    else
        log_error "  [ERROR] FRP container failed to start"
        log_gray "  Check logs: docker logs $CONTAINER_NAME"
        exit 1
    fi
}

show_summary() {
    log_info "\n[5/5] Startup complete"
    log_info "\n========================================"
    log_info " FRP Tunnel Mapping Information"
    log_info "========================================\n"
    
    echo -e "${NC}Local -> Remote:${NC}"
    log_gray "  Frontend: http://localhost:$FRONTEND_PORT -> http://${FRP_BASE_IP}:$REMOTE_FRONTEND_PORT"
    log_gray "  Backend:  http://localhost:$BACKEND_PORT -> http://${FRP_BASE_IP}:$REMOTE_BACKEND_PORT"
    
    echo -e "\n${NC}Domain Access:${NC}"
    log_gray "  Frontend: http://web.gymbro.cloud"
    log_gray "  Backend:  http://api.gymbro.cloud"
    
    echo -e "\n${NC}Management Commands:${NC}"
    log_gray "  View logs:    docker logs -f $CONTAINER_NAME"
    log_gray "  Stop service: docker stop $CONTAINER_NAME"
    log_gray "  Restart:      docker restart $CONTAINER_NAME"
    log_gray "  Remove:       docker rm -f $CONTAINER_NAME"
    
    log_info "\n========================================\n"
}

# Main Process
log_info "\n========================================"
log_info " FRP Client Docker Auto-Start Script"
log_info "========================================\n"

# Check Docker
check_docker

# Read environment variables
read_env_file

# Generate configuration
generate_frp_config

# Check local services
check_local_services

# Pull Docker image
pull_docker_image

# Start FRP container
start_frp_container

# Show summary
show_summary

log_success "FRP client started successfully!"

