#!/usr/bin/env bash
# setup.sh — Run once to bootstrap the entire project
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "======================================"
echo "  ProductHub — First-time Setup"
echo "======================================"
echo ""

# ── 1. Environment files ───────────────────────────────────────────────────────
echo "[1/7] Setting up environment files..."

if [ ! -f "$BACKEND/.env" ]; then
  cp "$ROOT/.env.example" "$BACKEND/.env"

  # Generate a random SECRET_KEY and substitute it in the copied .env
  if command -v openssl &>/dev/null; then
    SECRET=$(openssl rand -hex 32)
    sed -i "s/change-this-to-a-random-secret-key-in-production/$SECRET/" "$BACKEND/.env"
    echo "      Created backend/.env (SECRET_KEY auto-generated)"
  else
    echo "      Created backend/.env from .env.example"
    echo "      ⚠  Replace SECRET_KEY in backend/.env with a random value before deploying"
  fi
  echo "      ⚠  Edit backend/.env and add your API keys before running start.sh"
else
  echo "      backend/.env already exists — skipping"
fi

if [ ! -f "$FRONTEND/.env.local" ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > "$FRONTEND/.env.local"
  echo "      Created frontend/.env.local"
else
  echo "      frontend/.env.local already exists — skipping"
fi

# ── 2. Docker infrastructure ───────────────────────────────────────────────────
echo ""
echo "[2/7] Starting Postgres + Redis via Docker..."
docker compose -f "$ROOT/docker-compose.dev.yml" up -d
echo "      Waiting for Postgres to be ready..."
until docker compose -f "$ROOT/docker-compose.dev.yml" exec -T db pg_isready -U postgres -q 2>/dev/null; do
  sleep 1
done
echo "      Postgres is ready."

# ── 3. Python virtual environment ─────────────────────────────────────────────
echo ""
echo "[3/7] Setting up Python virtual environment..."
cd "$BACKEND"

if [ ! -d ".venv" ]; then
  python -m venv .venv
  echo "      Created .venv"
else
  echo "      .venv already exists — skipping"
fi

# Activate venv (works in Git Bash / bash on Windows)
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate   # Windows (Git Bash)
else
  source .venv/bin/activate        # macOS / Linux
fi

echo "      Installing Python dependencies..."
pip install -q -r requirements.txt

echo "      Installing Playwright browser (Chromium)..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# ── 4. Database migrations ─────────────────────────────────────────────────────
echo ""
echo "[4/7] Running database migrations..."
alembic upgrade head
echo "      Migrations complete."

# ── 5. Seed stub dev user ──────────────────────────────────────────────────────
echo ""
echo "[5/7] Seeding stub dev user..."
echo "      (dev@localhost.com / dev-password — auto-seeded on API startup)"

# ── 6. Frontend dependencies ───────────────────────────────────────────────────
echo ""
echo "[6/7] Installing frontend npm packages..."
cd "$FRONTEND"
npm install --silent

# ── 7. Done ────────────────────────────────────────────────────────────────────
echo ""
echo "[7/7] Setup complete!"
echo ""
echo "======================================"
echo "  Next steps:"
echo ""
echo "  1. Edit backend/.env and add:"
echo "     ANTHROPIC_API_KEY=sk-ant-..."
echo "     SHOPIFY_STORE_DOMAIN=your-store.myshopify.com"
echo "     SHOPIFY_CLIENT_ID=<from Dev Dashboard>"
echo "     SHOPIFY_CLIENT_SECRET=<from Dev Dashboard>"
echo ""
echo "  2. Run ./start.sh to start all services"
echo ""
echo "  Dev login: dev@localhost.com / dev-password"
echo "======================================"
echo ""
