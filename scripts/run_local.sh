#!/usr/bin/env bash
# ============================================================
# Takshashila Archive Intelligence — NO-DOCKER local run (macOS/Linux)
# SQLite + in-process jobs. No PostgreSQL, no Redis, no Docker.
# Usage:  ./scripts/run_local.sh
# ============================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Takshashila Archive Intelligence : local (no Docker) =="

command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
command -v node >/dev/null || { echo "node required"; exit 1; }

mkdir -p data

if [ ! -d .venv ]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi
echo "Installing backend dependencies (lean, no-Docker set)..."
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r apps/api/requirements-local.txt

if [ ! -f .env ]; then
  echo "Creating .env with a freshly generated APP_SECRET_KEY..."
  SECRET="$(.venv/bin/python -c 'import secrets;print(secrets.token_urlsafe(48))')"
  cat > .env <<EOF
DATABASE_URL=sqlite+pysqlite:///./data/dev.db
JOBS_INLINE=true
REDIS_URL=
DATA_DIR=./data
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
MAX_DOWNLOAD_MB=200
APP_SECRET_KEY=$SECRET
EMBEDDING_PROVIDER=none
EMBEDDING_DIMENSIONS=1024
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
EOF
  echo ".env created (secret NOT displayed)."
else
  echo ".env already exists — leaving it unchanged."
fi

echo "Starting API on http://localhost:8000 ..."
PYTHONPATH=apps/api CONFIG_DIR="$REPO_ROOT/config" \
  .venv/bin/uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 &
API_PID=$!

if [ ! -d apps/web/node_modules ]; then
  echo "Installing web dependencies (first run only)..."
  (cd apps/web && npm install)
fi
echo "Starting web UI on http://localhost:3000 ..."
(cd apps/web && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev) &
WEB_PID=$!

echo ""
echo "Running. Web: http://localhost:3000  |  API: http://localhost:8000/health /ready /docs"
echo "Press Ctrl+C to stop."
trap "kill $API_PID $WEB_PID 2>/dev/null || true" INT TERM
wait
