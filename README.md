# PaisaProof

> Investor literacy and financial claim verification platform. Educational only — no buy/sell/hold advice or stock recommendations.

- **Live Web:** https://aadha-ps.vercel.app
- **Architecture & Contracts:** [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md)
- **Team Progress:** [`STATUS.md`](STATUS.md)

## Stack & Hosting

| Layer | Technology | Hosting |
|---|---|---|
| **Web** | Next.js (App Router), TypeScript, Tailwind CSS, Recharts | Vercel (`apps/web`) |
| **API & Jobs** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | Render (`services/api`) |
| **Database & Platform** | Postgres, Managed Auth (EdDSA JWT), Object Storage, Realtime | Neon |
| **LLM & Market Data** | OpenRouter (`core.llm` + EN/Hinglish guardrails), split-adjusted NSE/BSE (`yfinance`) & Finnhub | Managed |
| **CI** | Ruff, Black, Mypy, ESLint, Prettier, TypeScript, Pytest, Next.js build | GitHub Actions |

## Quickstart

1. Copy the environment template and fill in your local credentials (never commit `.env*`):
   ```bash
   cp .env.example .env.local
   ```
   *(Optional local database: run `docker compose -f infra/docker-compose.yml up -d` if not targeting Neon directly.)*
2. Install backend and frontend dependencies:
   ```bash
   make setup
   ```
3. Run database migrations and validate/seed local data:
   ```bash
   make migrate && make seed
   ```
4. Start the FastAPI server (`:8000`) and Next.js web app (`:3000`):
   ```bash
   make dev
   ```

## Commands

| Command | Purpose |
|---|---|
| `make setup` | Create `services/api/.venv` (Python 3.11), install API dev deps, and install `apps/web` packages |
| `make dev` | Run FastAPI (`:8000`) and Next.js (`:3000`) concurrently |
| `make check` | Run the full local gate: `lint`, `typecheck`, `test`, and `build` |
| `make lint` | Run `ruff`, `black --check`, ESLint, and Prettier |
| `make typecheck` | Run `mypy` (`services/api/app`) and `tsc --noEmit` (`apps/web`) |
| `make test` | Run backend pytest suite (`services/api/tests`) |
| `make build` | Build Next.js production bundle (`apps/web`) |
| `make check-api` | Verify API `/health` and `/me` auth guard (`API_URL` defaults to `http://localhost:8000/api/v1`) |
| `make migrate` | Apply Alembic migrations (`alembic -c db/alembic.ini upgrade head`) |
| `make seed` | Validate and seed `data/seed/` records |
| `make cron` | Refresh market caches and score open verifier claims |

## API & Health Checks

Run the public platform probe against local or deployed API hosts:

```bash
# Public health + unauthenticated 401 guard
make check-api API_URL=https://<your-api-host>/api/v1

# Authenticated platform gate (/health + 401/200 /me)
PYTHONPATH=services/api services/api/.venv/bin/python infra/scripts/smoke_test.py \
  --base-url https://<your-api-host>/api/v1 \
  --platform-only \
  --jwt "<BEARER_JWT>"

# Minimal curl checks
curl -sf https://<your-api-host>/api/v1/health
curl -sf https://aadha-ps.vercel.app/api/neon/health
```

## Deployment

Required environment variable keys for all targets are documented in [`.env.example`](.env.example).

- **Neon:** Hosts Lakebase Postgres, Neon Auth (JWKS + trusted web origins), Object Storage, and Realtime.
- **Render:** Hosts the Python 3.11 FastAPI service (`alembic -c db/alembic.ini upgrade head && uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port $PORT`, health check `/api/v1/health`) and daily post-close cron (`infra/scripts/daily_job.py`).
- **Vercel:** Deploys the Next.js frontend from `apps/web` with Neon service bindings and `NEXT_PUBLIC_API_URL` pointing to the Render `/api/v1` base.

## Repository Layout & Ownership

```text
.
├── apps/web/               # Next.js frontend (Ananya)
├── services/api/
│   ├── app/core/           # Config, DB, Neon Auth, OpenRouter LLM, guardrails, market data (Hardhik)
│   ├── app/education/      # Onboarding, lessons, scenarios, assessments (Divyansh)
│   ├── app/verifier/       # Source verification & scoring (Arnav)
│   └── app/nasdaq_verifier/# Nasdaq literacy capstone
├── db/migrations/          # Alembic migrations (Hardhik)
├── data/seed/              # Market, education, and verifier seed data
└── infra/                  # Docker, Render blueprint, CI scripts
```

| Owner | Scope | Does NOT Touch |
|---|---|---|
| **Arnav** | `services/api/app/verifier/`, `data/seed/verifier/` | UI, `education/`, `infra/` |
| **Divyansh** | `services/api/app/education/`, `data/seed/education/` | UI, `verifier/`, `infra/` |
| **Hardhik** | `services/api/app/core/`, `main.py`, `infra/`, `db/`, `.github/`, `STATUS.md`, `data/seed/market/` | Feature logic in `education/` or `verifier/` |
| **Ananya** | `apps/web/` | Backend code, DB migrations |

## Git & Contract Rules

- **Branches:** `feat/verifier-*`, `feat/education-*`, `infra/*`, `ui/*` — open PRs into `main` with CI green.
- **Safety:** No force-push, no history rewrite, and never commit `.env*` files or credentials.
- **Contracts:** Propose changes to `docs/SOURCE_OF_TRUTH.md` via PRs titled `contract: ...` for integration owner review.
