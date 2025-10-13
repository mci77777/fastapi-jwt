#!/bin/bash
# FRP Client WSL Docker Start Script
# Purpose: Run FRP client in Docker with host network mode
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRP_DIR="$PROJECT_ROOT/frp"
FRP_CONFIG_FILE="$FRP_DIR/frpc.ini"
CONTAINER_NAME="frpc-gymbro"
IMAGE_NAME="fatedier/frpc:v0.52.3"

log_info "\n========================================"
log_info " FRP Client WSL Docker Start"
log_info "========================================\n"

# Step 1: Check Docker
log_info "[1/6] Checking Docker..."
if ! command -v docker &> /dev/null; then
    log_error "ERROR: Docker not installed"
    exit 1
fi

if ! docker ps &> /dev/null; then
    log_error "ERROR: Docker daemon not running"
    log_gray "  Start Docker: sudo systemctl start docker"
    exit 1
fi

log_success "  [OK] Docker is ready"

# Step 2: Check configuration file
log_info "\n[2/6] Checking configuration..."
if [ ! -f "$FRP_CONFIG_FILE" ]; then
    log_error "ERROR: Configuration file not found: $FRP_CONFIG_FILE"
    exit 1
fi

log_success "  [OK] Configuration file exists"
log_gray "  Config: $FRP_CONFIG_FILE"

# Show configuration (mask token)
log_gray "\n  Configuration preview:"
grep -E "server_addr|server_port|auth_token" "$FRP_CONFIG_FILE" | while read line; do
    if [[ $line == *"auth_token"* ]]; then
        masked=$(echo "$line" | sed 's/\(auth_token = \)\(.\{8\}\).*/\1\2.../')
        log_gray "    $masked"
    else
        log_gray "    $line"
    fi
done

# Step 3: Check local services
log_info "\n[3/6] Checking local services..."

frontend_running=false
backend_running=false

if nc -z localhost 3101 2>/dev/null; then
    log_success "  [OK] Frontend running (port 3101)"
    frontend_running=true
else
    log_warn "  [WARN] Frontend not running (port 3101)"
fi

if nc -z localhost 9999 2>/dev/null; then
    log_success "  [OK] Backend running (port 9999)"
    backend_running=true
else
    log_warn "  [WARN] Backend not running (port 9999)"
fi

if [ "$frontend_running" = false ] && [ "$backend_running" = false ]; then
    log_warn "\n  [WARN] No local services running"
    log_gray "  FRP tunnel will not work without local services"
    log_gray "  Suggestion: Start services first"
fi

# Step 4: Pull Docker image
log_info "\n[4/6] Pulling Docker image..."
log_gray "  Image: $IMAGE_NAME"

if docker image inspect "$IMAGE_NAME" &> /dev/null; then
    log_success "  [OK] Image already exists"
else
    log_gray "  Pulling image..."
    docker pull "$IMAGE_NAME"
    log_success "  [OK] Image pulled"
fi

# Step 5: Stop existing container
log_info "\n[5/6] Managing existing containers..."

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warn "  [WARN] Existing container found: $CONTAINER_NAME"
    log_gray "  Stopping and removing..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    log_success "  [OK] Old container removed"
else
    log_gray "  No existing container found"
fi

# Step 6: Start FRP container
log_info "\n[6/6] Starting FRP container..."

log_gray "  Container name: $CONTAINER_NAME"
log_gray "  Network mode: host (direct access to localhost)"
log_gray "  Config file: $FRP_CONFIG_FILE"

# Use host network mode so container can access localhost:3101 and localhost:9999
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --network host \
    -v "$(realpath "$FRP_CONFIG_FILE"):/etc/frp/frpc.ini:ro" \
    "$IMAGE_NAME" \
    -c /etc/frp/frpc.ini

sleep 5

# Verify container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    CONTAINER_ID=$(docker ps -q -f name="^${CONTAINER_NAME}$")
    log_success "  [OK] Container started (ID: ${CONTAINER_ID:0:12})"
    
    log_info "\n========================================"
    log_info " FRP Container Status"
    log_info "========================================\n"
    
    log_gray "Container logs (last 15 lines):"
    echo ""
    docker logs --tail 15 "$CONTAINER_NAME" 2>&1 | while read line; do
        if [[ $line == *"ERROR"* ]] || [[ $line == *"failed"* ]]; then
            log_error "  $line"
        elif [[ $line == *"WARN"* ]] || [[ $line == *"WARNING"* ]]; then
            log_warn "  $line"
        elif [[ $line == *"success"* ]] || [[ $line == *"login"* ]]; then
            log_success "  $line"
        else
            log_gray "  $line"
        fi
    done
    
    log_info "\n========================================"
    log_info " Management Commands"
    log_info "========================================\n"
    
    log_gray "View logs:    docker logs -f $CONTAINER_NAME"
    log_gray "Stop service: docker stop $CONTAINER_NAME"
    log_gray "Restart:      docker restart $CONTAINER_NAME"
    log_gray "Remove:       docker rm -f $CONTAINER_NAME"
    
    log_info "\n========================================"
    log_info " Remote Access (if connected)"
    log_info "========================================\n"
    
    log_gray "Frontend: http://74.113.96.240:3101"
    log_gray "Backend:  http://74.113.96.240:9999"
    log_gray "API Domain: http://api.gymbro.cloud"
    
    log_info "\n========================================\n"
    
    # Check if login was successful
    sleep 2
    if docker logs --tail 5 "$CONTAINER_NAME" 2>&1 | grep -q "login to server success"; then
        log_success "FRP client connected successfully!"
    else
        log_warn "FRP client started but connection status unclear"
        log_gray "Check logs with: docker logs -f $CONTAINER_NAME"
    fi
else
    log_error "  [ERROR] Container failed to start"
    log_gray "  Check logs: docker logs $CONTAINER_NAME"
    exit 1
fi

