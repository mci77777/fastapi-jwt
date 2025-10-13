# FRP Connection Diagnostic Script
# Purpose: Diagnose FRP connection issues
# Author: GymBro Team
# Date: 2025-01-13

$ErrorActionPreference = 'Continue'

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " FRP Connection Diagnostic" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

# Test 1: FRP Version
Write-ColorOutput "[Test 1] FRP Client Version" "Cyan"
cd frp
$version = .\frpc.exe --version 2>&1 | Select-Object -First 1
Write-ColorOutput "  Version: $version" "Gray"

# Test 2: Configuration File
Write-ColorOutput "`n[Test 2] Configuration File" "Cyan"
if (Test-Path "frpc.ini") {
    Write-ColorOutput "  [OK] frpc.ini exists" "Green"
    Write-ColorOutput "`n  Configuration content:" "Gray"
    Get-Content "frpc.ini" | ForEach-Object {
        if ($_ -match "token") {
            $masked = $_ -replace '(token\s*=\s*)(.{8}).*', '$1$2...'
            Write-ColorOutput "    $masked" "Gray"
        } else {
            Write-ColorOutput "    $_" "Gray"
        }
    }
} else {
    Write-ColorOutput "  [ERROR] frpc.ini not found" "Red"
}

# Test 3: Network Connectivity
Write-ColorOutput "`n[Test 3] Network Connectivity" "Cyan"
$serverAddr = "74.113.96.240"
$serverPort = 7000

Write-ColorOutput "  Testing TCP connection to ${serverAddr}:${serverPort}..." "Yellow"
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect($serverAddr, $serverPort)
    $tcpClient.Close()
    Write-ColorOutput "  [OK] Port $serverPort is reachable" "Green"
} catch {
    Write-ColorOutput "  [ERROR] Cannot connect to port $serverPort" "Red"
    Write-ColorOutput "  Error: $($_.Exception.Message)" "Red"
}

# Test 4: DNS Resolution
Write-ColorOutput "`n[Test 4] DNS Resolution" "Cyan"
try {
    $dnsResult = Resolve-DnsName -Name "api.gymbro.cloud" -ErrorAction Stop
    Write-ColorOutput "  [OK] api.gymbro.cloud resolves to: $($dnsResult.IPAddress)" "Green"
} catch {
    Write-ColorOutput "  [WARN] Cannot resolve api.gymbro.cloud" "Yellow"
}

# Test 5: Local Services
Write-ColorOutput "`n[Test 5] Local Services" "Cyan"
$ports = @(3101, 9999)
foreach ($port in $ports) {
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("127.0.0.1", $port)
        $connection.Close()
        Write-ColorOutput "  [OK] Port $port is listening" "Green"
    } catch {
        Write-ColorOutput "  [WARN] Port $port is not listening" "Yellow"
    }
}

# Test 6: Firewall Rules
Write-ColorOutput "`n[Test 6] Windows Firewall" "Cyan"
try {
    $firewallRules = Get-NetFirewallRule -DisplayName "*frp*" -ErrorAction SilentlyContinue
    if ($firewallRules) {
        Write-ColorOutput "  [OK] Found FRP firewall rules:" "Green"
        $firewallRules | ForEach-Object {
            Write-ColorOutput "    - $($_.DisplayName) ($($_.Enabled))" "Gray"
        }
    } else {
        Write-ColorOutput "  [WARN] No FRP firewall rules found" "Yellow"
        Write-ColorOutput "  This may block outbound connections" "Yellow"
    }
} catch {
    Write-ColorOutput "  [WARN] Cannot check firewall rules" "Yellow"
}

# Test 7: Verbose Connection Test
Write-ColorOutput "`n[Test 7] Verbose Connection Test" "Cyan"
Write-ColorOutput "  Starting FRP with verbose logging..." "Yellow"
Write-ColorOutput "  (This will run for 10 seconds)`n" "Gray"

$output = & .\frpc.exe -c frpc.ini 2>&1 | Select-Object -First 20
$output | ForEach-Object {
    if ($_ -match "ERROR|failed|shutdown") {
        Write-ColorOutput "  $_" "Red"
    } elseif ($_ -match "WARNING|WARN") {
        Write-ColorOutput "  $_" "Yellow"
    } elseif ($_ -match "success|login") {
        Write-ColorOutput "  $_" "Green"
    } else {
        Write-ColorOutput "  $_" "Gray"
    }
}

# Summary
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " Diagnostic Summary" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

Write-ColorOutput "Common Issues and Solutions:" "White"
Write-ColorOutput "`n1. 'session shutdown' error:" "Yellow"
Write-ColorOutput "   - Server may be using different FRP version" "Gray"
Write-ColorOutput "   - Token may be incorrect or expired" "Gray"
Write-ColorOutput "   - Server may require different auth method" "Gray"
Write-ColorOutput "   - IP may be blocked by firewall" "Gray"

Write-ColorOutput "`n2. Connection timeout:" "Yellow"
Write-ColorOutput "   - Check if port 7000 is open on server" "Gray"
Write-ColorOutput "   - Verify server IP address is correct" "Gray"
Write-ColorOutput "   - Check local firewall settings" "Gray"

Write-ColorOutput "`n3. Next Steps:" "Yellow"
Write-ColorOutput "   - Contact server administrator to verify:" "Gray"
Write-ColorOutput "     * FRP server version" "Gray"
Write-ColorOutput "     * Authentication method (token/oidc/etc)" "Gray"
Write-ColorOutput "     * Required client version" "Gray"
Write-ColorOutput "     * IP whitelist settings" "Gray"

Write-ColorOutput "`n4. Alternative Solutions:" "Yellow"
Write-ColorOutput "   - Try FRP v0.51.0 (older stable version)" "Gray"
Write-ColorOutput "   - Use ngrok or Cloudflare Tunnel instead" "Gray"
Write-ColorOutput "   - Set up VPN connection to server" "Gray"

Write-ColorOutput "`n========================================`n" "Cyan"

cd ..

