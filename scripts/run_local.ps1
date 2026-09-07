# ============================================================
# Takshashila Archive Intelligence — NO-DOCKER local run (Windows)
# SQLite + in-process jobs. No PostgreSQL, no Redis, no Docker.
#
# Usage (from the repo root, in PowerShell):
#     .\scripts\run_local.ps1
#
# It will: create a Python venv, install the lean deps, write a local .env
# (with a freshly generated APP_SECRET_KEY) if one does not exist, start the
# API on http://localhost:8000, install web deps, and start the web UI on
# http://localhost:3000 — each in its own window.
# ============================================================
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

Write-Host "== Takshashila Archive Intelligence : local (no Docker) ==" -ForegroundColor Magenta

# --- checks ---
function Need($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "$name is required but was not found on PATH. Install it and retry."
  }
}
Need python
Need node
Need npm

# --- data dir ---
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "data") | Out-Null

# --- python venv + deps ---
if (-not (Test-Path ".venv")) {
  Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
  python -m venv .venv
}
$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
Write-Host "Installing backend dependencies (lean, no-Docker set)..." -ForegroundColor Cyan
& $Py -m pip install --upgrade pip | Out-Null
& $Py -m pip install -r "apps\api\requirements-local.txt"

# --- .env (create if missing; never print the secret) ---
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
  Write-Host "Creating .env with a freshly generated APP_SECRET_KEY..." -ForegroundColor Cyan
  $bytes = New-Object byte[] 48
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $secret = [Convert]::ToBase64String($bytes)
  @"
DATABASE_URL=sqlite+pysqlite:///./data/dev.db
JOBS_INLINE=true
REDIS_URL=
DATA_DIR=./data
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
MAX_DOWNLOAD_MB=200
APP_SECRET_KEY=$secret
EMBEDDING_PROVIDER=none
EMBEDDING_DIMENSIONS=1024
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
"@ | Set-Content -Encoding UTF8 $EnvFile
  Write-Host ".env created (secret NOT displayed)." -ForegroundColor Green
} else {
  Write-Host ".env already exists — leaving it unchanged." -ForegroundColor Yellow
}

# --- start API in its own window ---
Write-Host "Starting API on http://localhost:8000 ..." -ForegroundColor Cyan
$apiCmd = "`$env:PYTHONPATH='apps\api'; `$env:CONFIG_DIR='$RepoRoot\config'; & '$Py' -m uvicorn app.main:app --app-dir apps\api --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit","-Command",$apiCmd -WorkingDirectory $RepoRoot

# --- web deps + start in its own window ---
if (-not (Test-Path "apps\web\node_modules")) {
  Write-Host "Installing web dependencies (first run only)..." -ForegroundColor Cyan
  Push-Location "apps\web"; npm install; Pop-Location
}
Write-Host "Starting web UI on http://localhost:3000 ..." -ForegroundColor Cyan
$webCmd = "`$env:NEXT_PUBLIC_API_BASE_URL='http://localhost:8000'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit","-Command",$webCmd -WorkingDirectory (Join-Path $RepoRoot "apps\web")

Write-Host ""
Write-Host "All set. Two windows are starting up (API + Web)." -ForegroundColor Green
Write-Host "  Web UI : http://localhost:3000" -ForegroundColor Green
Write-Host "  API    : http://localhost:8000/health  |  /ready  |  /docs" -ForegroundColor Green
Write-Host ""
Write-Host "Optional: load synthetic demo data (clearly labelled, not archival):" -ForegroundColor Cyan
Write-Host '  Invoke-RestMethod -Method Post http://localhost:8000/api/ingestion/demo/seed'
