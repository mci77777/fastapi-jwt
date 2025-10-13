# FRP Client Troubleshooting Guide

## Current Issue Summary

### Problem
FRP v0.61.1 client fails to start with error:
```
error unmarshaling JSON: while decoding JSON: json: cannot unmarshal string into Go value of type v1.ClientConfig
```

### Root Cause
FRP v0.61.1 has a bug where it attempts to parse TOML configuration files as JSON, causing the unmarshaling error. This affects both:
- Windows version (`frpc.exe`)
- Linux version (`frpc`)
- Docker images (both `fatedier/frpc:v0.61.1` and `snowdreamtech/frpc:0.61.1`)

### Verified Facts
1. ✅ Server port 7000 is accessible (`74.113.96.240:7000`)
2. ✅ Configuration file syntax is correct (TOML format)
3. ✅ Token and credentials are valid
4. ❌ FRP v0.61.1 TOML parser is broken

## Recommended Solutions

### Solution 1: Use FRP v0.52.3 (Stable Version)

**Windows (PowerShell):**
```powershell
# Download FRP v0.52.3
$FRP_VERSION = "0.52.3"
$ARCH = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
$URL = "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_windows_${ARCH}.zip"

# Download and extract
Invoke-WebRequest -Uri $URL -OutFile "frp_${FRP_VERSION}.zip"
Expand-Archive -Path "frp_${FRP_VERSION}.zip" -DestinationPath "frp_${FRP_VERSION}"
Copy-Item "frp_${FRP_VERSION}\frp_${FRP_VERSION}_windows_${ARCH}\*" -Destination "frp\" -Recurse -Force

# Start FRP client
cd frp
.\frpc.exe -c frpc.ini
```

**Linux/WSL (Bash):**
```bash
# Download FRP v0.52.3
FRP_VERSION="0.52.3"
wget https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz
tar -xzf frp_${FRP_VERSION}_linux_amd64.tar.gz
cp frp_${FRP_VERSION}_linux_amd64/frpc frp/
chmod +x frp/frpc

# Start FRP client
cd frp
./frpc -c frpc.ini
```

### Solution 2: Use INI Configuration Format

FRP v0.61.1 still supports INI format (though deprecated). Create `frp/frpc.ini`:

```ini
[common]
server_addr = 74.113.96.240
server_port = 7000
auth_token = c86dbea00a800f87935646a238a43e09
log_level = info
log_max_days = 3

[gymbro-backend]
type = tcp
local_ip = 127.0.0.1
local_port = 9999
remote_port = 9999

[gymbro-frontend]
type = tcp
local_ip = 127.0.0.1
local_port = 3101
remote_port = 3101

[gymbro-api-http]
type = http
local_ip = 127.0.0.1
local_port = 9999
custom_domains = api.gymbro.cloud

[gymbro-web-http]
type = http
local_ip = 127.0.0.1
local_port = 3101
custom_domains = web.gymbro.cloud
```

**Start with INI:**
```bash
# Windows
.\frp\frpc.exe -c frp\frpc.ini

# Linux/WSL
./frp/frpc -c frp/frpc.ini
```

### Solution 3: Wait for FRP v0.62.x or Use v0.60.0

Check for newer releases:
```bash
curl -s https://api.github.com/repos/fatedier/frp/releases/latest | grep tag_name
```

## Quick Fix Script

Create `scripts/start-frp-v052.ps1`:

```powershell
# FRP v0.52.3 Quick Start Script
$ErrorActionPreference = 'Stop'

$FRP_VERSION = "0.52.3"
$FRP_DIR = "frp"
$ENV_FILE = ".env"

# Read .env
$FRP_BASE_IP = (Get-Content $ENV_FILE | Select-String "^FRP_BASE_IP=" | ForEach-Object { $_ -replace 'FRP_BASE_IP=', '' -replace '"', '' })
$FRP_TOKEN = (Get-Content $ENV_FILE | Select-String "^FRP_TOKEN=" | ForEach-Object { $_ -replace 'FRP_TOKEN=', '' -replace '"', '' })

# Generate INI config
@"
[common]
server_addr = $FRP_BASE_IP
server_port = 7000
auth_token = $FRP_TOKEN
log_level = info

[gymbro-backend]
type = tcp
local_ip = 127.0.0.1
local_port = 9999
remote_port = 9999

[gymbro-frontend]
type = tcp
local_ip = 127.0.0.1
local_port = 3101
remote_port = 3101
"@ | Out-File -FilePath "$FRP_DIR\frpc.ini" -Encoding ASCII

Write-Host "Starting FRP client..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FRP_DIR'; .\frpc.exe -c frpc.ini"
Write-Host "[OK] FRP client started" -ForegroundColor Green
```

## Verification Steps

After starting FRP client:

1. **Check process:**
   ```powershell
   # Windows
   Get-Process -Name frpc
   
   # Linux
   ps aux | grep frpc
   ```

2. **Check logs:**
   ```bash
   # Look for successful connection
   # Should see: "login to server success"
   # Should see: "proxy added: [gymbro-backend]"
   # Should see: "proxy added: [gymbro-frontend]"
   ```

3. **Test remote access:**
   ```powershell
   # Test backend
   curl http://74.113.96.240:9999/api/v1/healthz
   
   # Test frontend
   curl http://74.113.96.240:3101
   ```

## Known Issues

### Issue 1: Docker Container `127.0.0.1` Problem
**Symptom:** `connect to local service [127.0.0.1:9999] error: connection refused`

**Solution:** Use `host.docker.internal` or host gateway IP:
```bash
docker run -d \
  --name frpc \
  --add-host=host.docker.internal:host-gateway \
  --network host \
  -v $(pwd)/frp/frpc.ini:/etc/frp/frpc.ini:ro \
  fatedier/frpc:v0.52.3 \
  -c /etc/frp/frpc.ini
```

### Issue 2: JWT Verification Failed (401)
**Symptom:** Backend logs show `JWT verification failed`

**Cause:** Requests through FRP tunnel don't include JWT token

**Solution:** This is expected for unauthenticated endpoints. For authenticated endpoints, ensure frontend includes token in requests.

## Contact & Support

- **FRP GitHub Issues:** https://github.com/fatedier/frp/issues
- **Project Documentation:** `docs/FRP_CLIENT_GUIDE.md`
- **Quick Reference:** `docs/FRP_QUICK_REFERENCE.md`

## Changelog

- **2025-01-13:** Initial troubleshooting guide created
- **Issue:** FRP v0.61.1 TOML parsing bug identified
- **Recommendation:** Use v0.52.3 or INI format until bug is fixed

