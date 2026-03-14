#!/usr/bin/env bash
# start.sh — Start all dev services (Docker, FastAPI, Celery, Next.js)
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# PIDs we'll track for cleanup
PIDS=()

cleanup() {
  echo ""
  echo "Shutting down services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  echo "Done."
}
trap cleanup EXIT INT TERM

# ── Activate Python venv ───────────────────────────────────────────────────────
if [ -f "$BACKEND/.venv/Scripts/activate" ]; then
  ACTIVATE="$BACKEND/.venv/Scripts/activate"   # Windows (Git Bash)
else
  ACTIVATE="$BACKEND/.venv/bin/activate"        # macOS / Linux
fi

if [ ! -f "$ACTIVATE" ]; then
  echo "Error: Python venv not found. Run ./setup.sh first."
  exit 1
fi

# ── Check .env ─────────────────────────────────────────────────────────────────
if [ ! -f "$BACKEND/.env" ]; then
  echo "Error: backend/.env not found. Run ./setup.sh first."
  exit 1
fi

echo ""
echo "======================================"
echo "  ProductHub — Starting Dev Services"
echo "======================================"
echo ""

# ── 1. Docker (Postgres + Redis) ───────────────────────────────────────────────
echo "[1/4] Starting Docker services..."
docker compose -f "$ROOT/docker-compose.dev.yml" up -d --quiet-pull 2>/dev/null || \
  docker compose -f "$ROOT/docker-compose.dev.yml" up -d

echo "      Waiting for Postgres..."
until docker compose -f "$ROOT/docker-compose.dev.yml" exec -T db pg_isready -U postgres -q 2>/dev/null; do
  sleep 1
done
echo "      Postgres ready."

# ── 2. FastAPI backend ─────────────────────────────────────────────────────────
echo ""
echo "[2/4] Starting FastAPI backend on :8000..."
(
  cd "$BACKEND"
  source "$ACTIVATE"
  uvicorn app.main:app --reload --port 8000 --log-level warning
) &
PIDS+=($!)

# Wait for FastAPI to be ready (stub user is seeded on startup)
echo "      Waiting for API..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "      API ready."
    break
  fi
  sleep 1
done

# ── 3. Celery worker + beat ────────────────────────────────────────────────────
echo ""
echo "[3/4] Starting Celery worker + beat..."
(
  cd "$BACKEND"
  source "$ACTIVATE"
  celery -A app.workers.celery_app worker \
    --loglevel=warning \
    -Q default,imports,enrichment,scraping,pricing,sync \
    --concurrency=4
) &
PIDS+=($!)

(
  cd "$BACKEND"
  source "$ACTIVATE"
  celery -A app.workers.celery_app beat \
    --loglevel=warning
) &
PIDS+=($!)

# ── 4. Next.js frontend ────────────────────────────────────────────────────────
echo ""
echo "[4/4] Starting Next.js frontend on :3000..."
# Clear .next cache to avoid Windows file-lock corruption (errno -4094)
if [ -d "$FRONTEND/.next" ]; then
  echo "      Clearing .next cache..."
  rm -rf "$FRONTEND/.next"
fi
(
  cd "$FRONTEND"
  npm run dev
) &
PIDS+=($!)

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "======================================"
echo "  All services running:"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "  Dev login: dev@localhost.com / dev-password"
echo ""
echo "  Press Ctrl+C to stop everything."
echo "======================================"
echo ""

# Wait for any process to exit
wait
