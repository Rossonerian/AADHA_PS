# Aacharya

> Source of truth for architecture, contracts, and team workflow: [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md).

## Quickstart

1. Copy environment template and fill in local values (never commit `.env`):
   ```bash
   cp .env.example .env
   ```
2. Start local PostgreSQL (if not using Supabase directly):
   ```bash
   docker compose -f infra/docker-compose.yml up -d
   ```
3. Install backend and frontend dependencies:
   ```bash
   make setup
   ```
4. Run database migrations and seed data:
   ```bash
   make migrate
   make seed
   ```
5. Start the API (`:8000`) and Next.js web app (`:3000`) together:
   ```bash
   make dev
   ```

## `make` Commands

| Command | Description |
|---|---|
| `make setup` | Create `services/api/.venv` (Python 3.11), install `services/api[dev]`, and run `cd apps/web && npm install` |
| `make dev` | Run FastAPI (`uvicorn` on `:8000`) and Next.js (`:3000`) concurrently with clean trap shutdown |
| `make lint` | Run `ruff`, `black --check`, `npm run lint`, and `npm run format:check` |
| `make typecheck` | Run `mypy services/api/app` and `cd apps/web && npm run typecheck` |
| `make test` | Run backend test suite (`pytest services/api/tests`) |
| `make migrate` | Apply Alembic migrations (`alembic -c db/alembic.ini upgrade head`) |
| `make seed` | Run seed script (`infra/scripts/seed.py`) |
| `make cron` | Run daily market/claim scoring job (`infra/scripts/daily_job.py`) |

## Folder Ownership

| Person | Owns | Code / Files | Does NOT touch |
|---|---|---|---|
| **Arnav** | Verifier backend & features | `services/api/app/verifier/`, `data/seed/verifier/` | UI, education module, infra |
| **Divyansh** | Education backend & features | `services/api/app/education/`, `data/seed/education/` | UI, verifier module, infra |
| **Hardhik** | Deployment, setup, status, shared core | `services/api/app/core/`, `services/api/app/main.py`, `infra/`, `db/`, `.github/`, `STATUS.md`, `data/seed/market/` | Feature logic inside `education/` or `verifier/` |
| **Ananya** | Complete UI | `apps/web/` | Backend code, DB |

## Git & Contract Rules

- **Branch naming**: Use your area prefix — `feat/verifier-*`, `feat/education-*`, `infra/*`, `ui/*`.
- **Pull Requests**: Always PR into `main`; CI (`lint`, `typecheck`, `tests`, `build`) must pass before merge.
- **Git safety**: No force-push, no history rewrite, no deleting others' branches, and never commit `.env` or API keys.
- **Contract changes**: Propose changes to `docs/SOURCE_OF_TRUTH.md` via a PR titled `contract: ...`. Hardhik (contract & integration owner) reviews, approves, and updates the Source of Truth.
