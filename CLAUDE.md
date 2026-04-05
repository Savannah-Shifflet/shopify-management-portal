# ProductHub — Claude Code Reference

E-commerce product management app for authorized dealers. AI-enriched product uploads, Shopify sync, supplier relationship management, and pricing automation.

---

## Rules

- Always ask clarifying questions before complex or multi-file tasks
- Never run `npx shadcn@latest` — Node 18 on this machine, shadcn CLI requires Node 20+
- Never commit secrets, never skip `--no-verify`, never force-push main
- All DB queries must filter by `user_id == current_user.id` — multi-tenant, each user owns their data
- AI suggestions always land in `ai_*` staging columns; never auto-apply to main fields without user acceptance

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui (manual install), TanStack Query v5 |
| Backend | Python FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| AI | Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Workers | Celery + Redis (queues: default, imports, enrichment, scraping, pricing, sync) |
| Database | PostgreSQL 16 |
| Scraping | Playwright + BeautifulSoup |
| Shopify | REST API + GraphQL (API version 2025-01) |

---

## Setup

```bash
# Infrastructure
docker compose -f docker-compose.dev.yml up -d

# Backend
cd backend
.venv/Scripts/alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Workers
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info

# Tests
cd backend && pytest tests/
```

**Dev credentials**: `dev@localhost.com` / `dev-password` (UUID `00000000-0000-0000-0000-000000000001`, auto-seeded on startup — gate behind `DEV_MODE=true` before production)

---

## Key File Paths

```
backend/app/
  main.py              # FastAPI entry, router registration
  database.py          # SQLAlchemy engine, SessionLocal, Base
  dependencies.py      # get_current_user JWT dependency
  config.py            # Settings from .env
  models/              # SQLAlchemy ORM models (one file per model)
  schemas/product.py   # All product-related Pydantic schemas
  routers/             # One file per feature area
  services/
    enrichment_service.py   # Claude AI enrichment logic
    pricing_service.py      # Pricing rule evaluation + record_price_history()
    ai_acceptance.py        # Universal AI field acceptance utility (ACCEPTANCE_MAP)
    scrape_service.py       # Supplier selector testing + AI suggestions
  workers/             # Celery tasks (see backend/app/workers/CLAUDE.md)
  utils/
    claude_client.py        # Anthropic SDK wrapper (sync + async clients)
    shopify_client.py       # Shopify REST + GraphQL client

frontend/src/
  app/                 # Next.js pages (see frontend/CLAUDE.md)
  components/ui/       # shadcn/ui primitives
  lib/api.ts           # All API client functions
  lib/auth.ts          # JWT storage helpers
```

---

## Reference Docs

Detailed reference is split into subdirectory CLAUDE.md files (auto-loaded when working in that directory) and `.claude/` docs (load on demand):

| What | Where |
|---|---|
| DB models, API routes, migrations, env vars | `backend/CLAUDE.md` |
| Celery tasks, beat schedule, worker patterns | `backend/app/workers/CLAUDE.md` |
| Frontend pages, API client, component patterns | `frontend/CLAUDE.md` |
| Architecture decisions, AI enrichment, Shopify sync | `.claude/architecture.md` |
| Pricing feature reference | `.claude/pricing.md` |
| Production checklist, open issues, app store gates | `.claude/production-checklist.md` |
| Workflows (new feature, add AI field, deploy) | `.claude/workflows/` |
