# ============================================================
# Takshashila Archive Intelligence - NO-DOCKER local run (Windows)
# SQLite + in-process jobs. No PostgreSQL, no Redis, no Docker.
#
# Usage (from the repo root, in PowerShell):
#     .\scripts\run_local.ps1
#
# Compatible with Windows PowerShell 5.1 and PowerShell 7+.
# This file is intentionally ASCII-only so PowerShell 5.1 (which reads .ps1 as
# the system ANSI code page when there is no BOM) parses every string correctly.
# ============================================================
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

Write-Host "== Takshashila Archive Intelligence : local (no Docker) ==" -ForegroundColor Magenta

# --- prerequisite checks (fail clearly) ---
function Test-Requirement($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw ("Required command not found on PATH: {0}. Install it and re-run." -f $name)
  }
}
Test-Requirement "python"
Test-Requirement "node"
Test-Requirement "npm"

# --- data directory ---
$DataDir = Join-Path $RepoRoot "data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# --- Python virtual environment ---
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvScripts = Join-Path $VenvDir "Scripts"
$Py = Join-Path $VenvScripts "python.exe"
if (-not (Test-Path -LiteralPath $Py)) {
  Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
  python -m venv $VenvDir
}
if (-not (Test-Path -LiteralPath $Py)) {
  throw "Virtual environment Python not found at: $Py"
}

# --- backend dependencies (lean, no-Docker set) ---
Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
$Req = Join-Path $RepoRoot "apps\api\requirements-local.txt"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r $Req

# --- .env (create if missing; never print the secret) ---
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path -LiteralPath $EnvFile)) {
  Write-Host "Creating .env with a freshly generated APP_SECRET_KEY..." -ForegroundColor Cyan
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $bytes = New-Object 'System.Byte[]' 48
  $rng.GetBytes($bytes)
  $secret = [Convert]::ToBase64String($bytes)
  $envLines = @(
    "DATABASE_URL=sqlite+pysqlite:///./data/dev.db",
    "JOBS_INLINE=true",
    "REDIS_URL=",
    "DATA_DIR=./data",
    "API_HOST=127.0.0.1",
    "API_PORT=8000",
    "CORS_ORIGINS=http://localhost:3000",
    "MAX_DOWNLOAD_MB=200",
    ("APP_SECRET_KEY=" + $secret),
    "EMBEDDING_PROVIDER=none",
    "EMBEDDING_DIMENSIONS=1024",
    "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000"
  )
  # ASCII encoding => no BOM, so python-dotenv reads the first key correctly.
  Set-Content -LiteralPath $EnvFile -Value $envLines -Encoding Ascii
  Write-Host ".env created (secret NOT displayed)." -ForegroundColor Green
} else {
  Write-Host ".env already exists - leaving it unchanged." -ForegroundColor Yellow
}

# --- make the venv tools + config visible to the child windows ---
# Environment changes here are inherited by processes started with Start-Process.
$env:Path = $VenvScripts + ";" + $env:Path
$env:PYTHONPATH = Join-Path $RepoRoot "apps\api"
$env:CONFIG_DIR = Join-Path $RepoRoot "config"

# --- start the API in its own window (cmd /k keeps it open) ---
Write-Host "Starting API on http://localhost:8000 ..." -ForegroundColor Cyan
$apiArgs = "/k uvicorn app.main:app --app-dir apps\api --host 127.0.0.1 --port 8000"
Start-Process -FilePath "cmd.exe" -ArgumentList $apiArgs -WorkingDirectory $RepoRoot

# --- web dependencies + start in its own window ---
$WebDir = Join-Path $RepoRoot "apps\web"
if (-not (Test-Path -LiteralPath (Join-Path $WebDir "node_modules"))) {
  Write-Host "Installing web dependencies (first run only)..." -ForegroundColor Cyan
  Push-Location -LiteralPath $WebDir
  npm install
  Pop-Location
}
Write-Host "Starting web UI on http://localhost:3000 ..." -ForegroundColor Cyan
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k npm run dev" -WorkingDirectory $WebDir

Write-Host ""
Write-Host "All set. Two windows are starting (API + Web)." -ForegroundColor Green
Write-Host "  Web UI : http://localhost:3000" -ForegroundColor Green
Write-Host "  API    : http://localhost:8000/health | /ready | /docs" -ForegroundColor Green
Write-Host ""
Write-Host "Optional: load synthetic demo data (labelled, not archival):" -ForegroundColor Cyan
Write-Host "  Invoke-RestMethod -Method Post http://localhost:8000/api/ingestion/demo/seed"
