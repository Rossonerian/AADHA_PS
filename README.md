# PaisaProof

> Investor literacy and financial claim verification platform. Educational only — no buy/sell/hold advice or stock recommendations.

- **Live Web:** https://aadha-ps.vercel.app
- **Architecture & Contracts:** [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md)
- **Team Progress:** [`STATUS.md`](STATUS.md)

## How it works (and what the AI does not do)

- **Educational half:** onboarding quiz with confidence ratings, a level (L1–L4) from accuracy and Brier calibration, a learning plan, lessons, historical scenarios and level-up assessments. Tools unlock by level; the server enforces the gates.
- **Verifier half:** a pasted tip is turned into a structured claim (symbol, direction, entry/target/stop, deadline). **The language model is used only for this extraction step** (`app/verifier/extraction.py`), and a claim is accepted only if it is grounded in a verbatim excerpt of the source text; otherwise it goes to review.
- **Everything after extraction is deterministic:** red flags (`app/verifier/red_flags.py`) and claim outcomes and source ratings (`app/verifier/scoring.py`) come from price data, surveillance and SEBI lists, and fixed rules. The model never produces a verdict, a number or a rating.
- **Scoring over time:** logged claims are scored against adjusted market prices by the daily job (`make cron`), so a source's label reflects its track record, not an opinion.
- **No advice, ever:** every generated text passes `core.guardrails.check_output()` (English and Hinglish); the product never says buy, sell or hold.
- **Nasdaq literacy capstone** (`app/nasdaq_verifier`): an optional Level-4 extension that reuses the same calibration idea on US data. The core product is India and NSE.
- **Data labels:** every record carries `data_origin: real | synthetic`, and the UI shows it.

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
3. Run database migrations and load content seed tables (questions, lessons, scenarios, stock explainers — never fake users):
   ```bash
   make migrate && make seed
   ```
4. Start the FastAPI server (`:8000`) and Next.js web app (`:3000`):
   ```bash
   make dev
   ```

## First-Test User Path (No Demo/Seed Users)

Fresh accounts are created exclusively via **Neon Auth sign-up** (`POST /api/auth/sign-up/email` on Vercel or through the landing page sign-in/sign-up flow). On the first authenticated request to `/api/v1/me` or any feature route, `core.auth.current_user()` verifies the Neon Auth EdDSA JWT against `NEON_AUTH_JWKS_URL` and auto-provisions the row in `public.users` at Level 1.

`infra/scripts/seed.py` validates dataset `data_origin` tags and loads **content tables only** (`questions`, `lessons`, `scenarios`, `edu_explain_cache`). Offline study/persona user fixtures (`study_seed.yaml`, `data/seed/verifier/seed.py`) are excluded from production seeding.

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
| `make seed` | Validate `data/seed/` and load Education content tables (`questions`, `lessons`, `scenarios`, `edu_explain_cache`) |
| `make cron` | Refresh market caches and score open verifier claims |

## API & Health Checks

```bash
# Public health + unauthenticated 401 guard + market freshness check
make check-api API_URL=https://<your-api-host>/api/v1

# Full fresh-user staging walkthrough (onboarding -> plan -> lesson -> assessment -> scenario -> explain -> verify -> dashboard)
PYTHONPATH=services/api services/api/.venv/bin/python infra/scripts/smoke_test.py \
  --base-url https://<your-api-host>/api/v1 \
  --auth-base-url https://aadha-ps.vercel.app/api/auth \
  --origin https://aadha-ps.vercel.app \
  --fresh-user --cleanup-db --timeout 75

# Minimal curl checks (/api/neon/health and /api/neon/verify are dev-only diagnostics intended to return 403 in production)
curl -sf https://<your-api-host>/api/v1/health
curl -sfI https://aadha-ps.vercel.app
```

## Cron, Stale-Refresh Alerting & Rate Limits

- **Daily Cron:** Scheduled on Render via `infra/render.yaml` at `0 13 * * 1-5` (`13:00 UTC` / `18:30 IST`, post-NSE close) running `infra/scripts/daily_job.py` (refreshes `core.market` caches, calls `verifier.score_open_claims()`, and logs a `daily_job` row in `job_runs`).
- **Stale Market Alerting:** `GET /api/v1/health` checks `market_data_as_of` against `MARKET_DATA_MAX_STALE_DAYS` (default `5`) and emits a structured `WARNING` log (`market_data_stale`) if stale or missing; `smoke_test.py --max-stale-days 5` fails fast if `market_data_as_of` is stale.
- **Rate Limits & Body Caps:** Sliding-window per-user and per-IP rate limits (`429 RATE_LIMITED` + `Retry-After`) protect `/api/v1/verify`, `/api/v1/nasdaq-verifier/submit`, `/api/v1/nasdaq-verifier/challenge`, `/api/v1/explain`, `/api/v1/assessments/*/submit`, `/api/v1/study/*/submit`, `/api/v1/scenarios/*/answer`, and `/api/v1/onboarding/answer` while keeping `/health` and `/me` exempt. Request bodies are capped at `MAX_REQUEST_BODY_BYTES` (`1 MiB` default) and `MAX_VERIFY_BODY_BYTES` (`10 MiB` on `/verify`), returning `413 PAYLOAD_TOO_LARGE`.

## Environment Variables

Templates with safe placeholder values live in [`.env.example`](.env.example).

| Variable | Target | Purpose |
|---|---|---|
| `APP_ENV`, `APP_VERSION` | Render, Local | Runtime environment (`production`/`development`) and reported API version |
| `CORS_ORIGINS` | Render, Local | Comma-separated allowed web origins (include `https://aadha-ps.vercel.app`) |
| `DATABASE_URL` | Render, Vercel, Local | Pooled Neon Postgres connection string |
| `DATABASE_URL_UNPOOLED` | Render, Local | Direct non-pooled Neon Postgres URL used by Alembic migrations & cleanup |
| `NEON_AUTH_BASE_URL` | Render, Vercel, Local | Neon Managed Better Auth endpoint URL |
| `NEON_AUTH_JWKS_URL` | Render, Vercel, Local | JWKS endpoint used by FastAPI to verify EdDSA JWTs |
| `NEON_AUTH_COOKIE_SECRET` | Vercel, Local | 32-byte cookie encryption secret for `@neon/auth` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `AWS_REGION` | Vercel, Local | Neon S3-compatible Object Storage credentials (`assets` bucket) |
| `NEON_REALTIME_URL`, `NEON_REALTIME_SECRET`, `NEXT_PUBLIC_NEON_REALTIME_URL` | Vercel, Local | Neon Realtime WebSocket endpoint and signing secret |
| `OPENROUTER_API_KEY`, `OPENROUTER_DEFAULT_MODEL`, `OPENROUTER_BASE_URL` | Render, Local | OpenRouter LLM credentials and model (`nvidia/nemotron-3.5-lightning:free`) |
| `FINNHUB_API_KEY` | Render, Local | Finnhub factual quotes/profile key for `/api/v1/nasdaq-verifier/*` |
| `MARKET_DATA_DIR`, `MARKET_DATA_MAX_STALE_DAYS` | Render, Local | Seed/cache path (`data/seed/market`) and stale-refresh warning threshold |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_WINDOW_SECONDS`, `RATE_LIMIT_USER_PER_WINDOW`, `RATE_LIMIT_IP_PER_WINDOW` | Render, Local | Sliding-window rate limiter configuration (`true`, `60s`, `20/user`, `60/IP`) |
| `MAX_REQUEST_BODY_BYTES`, `MAX_VERIFY_BODY_BYTES` | Render, Local | Payload size caps (`1048576` default, `10485760` `/verify`) |
| `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_USE_MOCKS` | Vercel, Local | Web origin, Render `/api/v1` base URL, and `false` to disable staging mocks |

## Deployment

- **Neon:** Hosts Lakebase Postgres, Neon Auth (JWKS + `https://aadha-ps.vercel.app` trusted origin), Object Storage, and Realtime.
- **Render:** Hosts the Python 3.11 FastAPI service (`alembic -c db/alembic.ini upgrade head && uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port $PORT`, health check `/api/v1/health`) and daily cron (`infra/scripts/daily_job.py`).
- **Vercel:** Deploys Next.js from `apps/web` with Neon service env vars, `NEXT_PUBLIC_USE_MOCKS=false`, and `NEXT_PUBLIC_API_URL` pointing to the Render `/api/v1` base.

### Google OAuth & Neon Auth Setup (Human Console Step)

"Continue with Google" uses Neon Managed Better Auth (`authClient.signIn.social({ provider: "google" })`) and requires one-time console configuration outside git:

1. In the **Neon Console**, open **Project → Auth → Providers → Google** and copy the **Authorized redirect URI** shown for your Neon Auth instance.
2. In **Google Cloud Console**, open **APIs & Services → Credentials → Create Credentials → OAuth client ID** (`Web application`), add the Neon Auth callback URL to **Authorized redirect URIs**, and save the generated Client ID and Client Secret.
3. Back in the **Neon Console** Google provider panel, paste the Google Client ID and Client Secret and enable the Google provider.
4. Under **Neon Console → Auth → Domains / Trusted Origins**, add `http://localhost:3000`, `https://aadha-ps.vercel.app`, and any Vercel preview domains you test on.

No extra Next.js or FastAPI environment variables are needed beyond `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL`, and `NEON_AUTH_COOKIE_SECRET` (Google OAuth secrets live exclusively in the Neon Auth console).

## Repository Layout & Ownership

```text
.
├── apps/web/               # Next.js frontend (Ananya)
├── services/api/
│   ├── app/core/           # Config, DB, Neon Auth, OpenRouter, Finnhub, guardrails, market, rate limits (Hardhik)
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
