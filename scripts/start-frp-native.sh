#!/bin/bash
# FRP Client Native Start Script (WSL/Linux)
# Purpose: Run FRP client natively without Docker
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
FRP_VERSION="0.61.1"
FRP_DOWNLOAD_BASE="https://github.com/fatedier/frp/releases/download"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRP_DIR="$PROJECT_ROOT/frp"
FRP_EXECUTABLE="$FRP_DIR/frpc"
FRP_CONFIG_FILE="$FRP_DIR/frpc.toml"
ENV_FILE="$PROJECT_ROOT/.env"
PID_FILE="$FRP_DIR/frpc.pid"

# Ports
FRONTEND_PORT=3101
BACKEND_PORT=9999

log_info "\n========================================"
log_info " FRP Client Native Start Script"
log_info "========================================\n"

# Step 1: Read .env
log_info "[1/6] Reading configuration..."

if [ ! -f "$ENV_FILE" ]; then
    log_error "ERROR: .env file not found: $ENV_FILE"
    exit 1
fi

FRP_BASE_IP=$(grep "^FRP_BASE_IP=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
FRP_TOKEN=$(grep "^FRP_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$FRP_BASE_IP" ] || [ -z "$FRP_TOKEN" ]; then
    log_error "ERROR: Missing FRP_BASE_IP or FRP_TOKEN in .env"
    exit 1
fi

log_gray "  Server: $FRP_BASE_IP"
log_gray "  Token: ${FRP_TOKEN:0:8}..."
log_success "  [OK] Configuration loaded"

# Step 2: Download FRP if needed
log_info "\n[2/6] Checking FRP client..."

if [ ! -f "$FRP_EXECUTABLE" ]; then
    log_warn "  FRP client not found, downloading..."
    
    mkdir -p "$FRP_DIR"
    
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) FRP_ARCH="amd64" ;;
        aarch64) FRP_ARCH="arm64" ;;
        armv7l) FRP_ARCH="arm" ;;
        *) log_error "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    
    OS="linux"
    FILENAME="frp_${FRP_VERSION}_${OS}_${FRP_ARCH}.tar.gz"
    DOWNLOAD_URL="$FRP_DOWNLOAD_BASE/v${FRP_VERSION}/$FILENAME"
    
    log_gray "  Downloading: $DOWNLOAD_URL"
    
    cd /tmp
    wget -q --show-progress "$DOWNLOAD_URL" || curl -L -O "$DOWNLOAD_URL"
    
    log_gray "  Extracting..."
    tar -xzf "$FILENAME"
    
    EXTRACTED_DIR="frp_${FRP_VERSION}_${OS}_${FRP_ARCH}"
    cp "$EXTRACTED_DIR/frpc" "$FRP_EXECUTABLE"
    chmod +x "$FRP_EXECUTABLE"
    
    rm -rf "$FILENAME" "$EXTRACTED_DIR"
    
    log_success "  [OK] FRP client downloaded"
else
    log_success "  [OK] FRP client already installed"
fi

log_gray "  Version: $($FRP_EXECUTABLE --version 2>&1 | head -1 || echo 'Unknown')"

# Step 3: Generate configuration
log_info "\n[3/6] Generating configuration..."

cat > "$FRP_CONFIG_FILE" <<EOF
# FRP Client Configuration
# Auto-generated at $(date '+%Y-%m-%d %H:%M:%S')

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
localIP = "127.0.0.1"
localPort = $BACKEND_PORT
remotePort = $BACKEND_PORT

# Frontend service (Vue3 on port 3101)
[[proxies]]
name = "gymbro-frontend"
type = "tcp"
localIP = "127.0.0.1"
localPort = $FRONTEND_PORT
remotePort = $FRONTEND_PORT

# HTTP proxy for API domain
[[proxies]]
name = "gymbro-api-http"
type = "http"
localIP = "127.0.0.1"
localPort = $BACKEND_PORT
customDomains = ["api.gymbro.cloud"]

# HTTP proxy for Web domain
[[proxies]]
name = "gymbro-web-http"
type = "http"
localIP = "127.0.0.1"
localPort = $FRONTEND_PORT
customDomains = ["web.gymbro.cloud"]
EOF

log_success "  [OK] Configuration generated: $FRP_CONFIG_FILE"

# Step 4: Check local services
log_info "\n[4/6] Checking local services..."

frontend_running=false
backend_running=false

if nc -z localhost $FRONTEND_PORT 2>/dev/null; then
    log_success "  [OK] Frontend running (port $FRONTEND_PORT)"
    frontend_running=true
else
    log_warn "  [WARN] Frontend not running (port $FRONTEND_PORT)"
fi

if nc -z localhost $BACKEND_PORT 2>/dev/null; then
    log_success "  [OK] Backend running (port $BACKEND_PORT)"
    backend_running=true
else
    log_warn "  [WARN] Backend not running (port $BACKEND_PORT)"
fi

if [ "$frontend_running" = false ] && [ "$backend_running" = false ]; then
    log_warn "\n  [WARN] No local services running"
    read -p "  Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "  Cancelled"
        exit 0
    fi
fi

# Step 5: Stop existing process
log_info "\n[5/6] Checking existing FRP process..."

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log_warn "  [WARN] Existing process found (PID: $OLD_PID)"
        read -p "  Kill and restart? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill "$OLD_PID" 2>/dev/null || true
            sleep 2
            log_success "  [OK] Old process terminated"
        else
            log_warn "  Cancelled"
            exit 0
        fi
    fi
    rm -f "$PID_FILE"
fi

# Step 6: Start FRP client
log_info "\n[6/6] Starting FRP client..."

nohup "$FRP_EXECUTABLE" -c "$FRP_CONFIG_FILE" > "$FRP_DIR/frpc.log" 2>&1 &
FRP_PID=$!
echo $FRP_PID > "$PID_FILE"

sleep 3

if kill -0 "$FRP_PID" 2>/dev/null; then
    log_success "  [OK] FRP client started (PID: $FRP_PID)"
    
    log_info "\n========================================"
    log_info " FRP Tunnel Information"
    log_info "========================================\n"
    
    log_gray "Process ID: $FRP_PID"
    log_gray "Config file: $FRP_CONFIG_FILE"
    log_gray "Log file: $FRP_DIR/frpc.log"
    
    log_info "\nRemote Access:"
    log_gray "  Frontend: http://${FRP_BASE_IP}:${FRONTEND_PORT}"
    log_gray "  Backend:  http://${FRP_BASE_IP}:${BACKEND_PORT}"
    log_gray "  API Domain: http://api.gymbro.cloud"
    
    log_info "\nManagement Commands:"
    log_gray "  View logs:    tail -f $FRP_DIR/frpc.log"
    log_gray "  Stop service: kill $FRP_PID"
    log_gray "  Restart:      bash $0"
    
    log_info "\n========================================\n"
    log_success "FRP client started successfully!"
    
    log_gray "\nShowing last 10 lines of log:"
    tail -10 "$FRP_DIR/frpc.log" 2>/dev/null || log_gray "  (Log file not ready yet)"
else
    log_error "  [ERROR] FRP client failed to start"
    log_gray "  Check log: cat $FRP_DIR/frpc.log"
    exit 1
fi

