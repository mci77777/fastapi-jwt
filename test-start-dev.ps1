# Test script for start-dev.ps1 validation
# This script validates the start-dev.ps1 without actually starting services

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Testing start-dev.ps1 Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check if start-dev.ps1 exists
Write-Host "[Test 1/6] Checking start-dev.ps1 exists..." -ForegroundColor Yellow
$scriptPath = Join-Path $PSScriptRoot "start-dev.ps1"
if (Test-Path $scriptPath) {
    Write-Host "  [PASS] start-dev.ps1 found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] start-dev.ps1 not found at: $scriptPath" -ForegroundColor Red
    exit 1
}

# Test 2: Check if run.py exists
Write-Host ""
Write-Host "[Test 2/6] Checking run.py exists..." -ForegroundColor Yellow
$runPyPath = Join-Path $PSScriptRoot "run.py"
if (Test-Path $runPyPath) {
    Write-Host "  [PASS] run.py found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] run.py not found at: $runPyPath" -ForegroundColor Red
    exit 1
}

# Test 3: Check if web directory exists
Write-Host ""
Write-Host "[Test 3/6] Checking web directory exists..." -ForegroundColor Yellow
$webPath = Join-Path $PSScriptRoot "web"
if (Test-Path $webPath) {
    Write-Host "  [PASS] web directory found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] web directory not found at: $webPath" -ForegroundColor Red
    exit 1
}

# Test 4: Check Python installation
Write-Host ""
Write-Host "[Test 4/6] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  [PASS] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Python not found in PATH" -ForegroundColor Red
    Write-Host "  Install Python 3.11+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Test 5: Check pnpm installation
Write-Host ""
Write-Host "[Test 5/6] Checking pnpm installation..." -ForegroundColor Yellow
try {
    $pnpmVersion = pnpm --version 2>&1
    Write-Host "  [PASS] pnpm found: v$pnpmVersion" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] pnpm not found in PATH" -ForegroundColor Red
    Write-Host "  Install with: npm install -g pnpm" -ForegroundColor Yellow
    exit 1
}

# Test 6: Validate start-dev.ps1 syntax
Write-Host ""
Write-Host "[Test 6/6] Validating PowerShell syntax..." -ForegroundColor Yellow
try {
    $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content $scriptPath -Raw), [ref]$null)
    Write-Host "  [PASS] PowerShell syntax is valid" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] PowerShell syntax error: $_" -ForegroundColor Red
    exit 1
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All Tests Passed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The start-dev.ps1 script is ready to use." -ForegroundColor Cyan
Write-Host "Run it with: .\start-dev.ps1" -ForegroundColor Cyan
Write-Host ""
