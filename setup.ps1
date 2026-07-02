#!/usr/bin/env pwsh
# One-command setup for VBU-Projects-Agent (Windows / PowerShell).
# Safe to re-run.
$ErrorActionPreference = "Stop"
# Ensure rich/console output (✓, →) encodes on legacy Windows consoles.
$env:PYTHONIOENCODING = "utf-8"
$pkg = Join-Path $PSScriptRoot "vbu-projects-agent"

Write-Host "==> Checking Python..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python 3.11+ is required but was not found. Install from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
    exit 1
}

Set-Location $pkg

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "==> Installing the vbu-agent package..." -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".venv\Scripts\python.exe" -m pip install -e .

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
}

Write-Host "==> Running diagnostics..." -ForegroundColor Cyan
& ".venv\Scripts\vbu-agent.exe" doctor

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. cd vbu-projects-agent"
Write-Host "  2. Activate the venv:  .venv\Scripts\Activate.ps1"
Write-Host "  3. Edit .env and set ANTHROPIC_API_KEY"
Write-Host "  4. Add your project:  vbu-agent project new --project my-project --name ""My Project"""
