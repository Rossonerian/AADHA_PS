# Aacharya — Team Status

> Updated by everyone in their own section; summarised by **Hardhik** after each checkpoint.
> Progress update format and checkpoint rules: [`docs/SOURCE_OF_TRUTH.md` Section 12](docs/SOURCE_OF_TRUTH.md#12-progress-updates-all-agents).

## Team Summary

| Person | % | Phase | Blockers | Last Update |
|---|---|---|---|---|
| Hardhik | 80% | Phase 4/6 (CI & Deploy — Neon postgres/auth/storage/realtime live; Phases 1,2,3,5 done) | Render/Vercel deploy URLs, OPENROUTER_API_KEY in cloud, docs/PRD.md export | 2026-11-20 |
| Arnav | 0% | Phase 1/6 (unblocked: core stubs & market/guardrails/llm ready) | none | 2026-11-20 |
| Divyansh | 0% | Phase 1/6 (unblocked: core stubs & auth/db ready) | none | 2026-11-20 |
| Ananya | 0% | Phase 1/6 (unblocked: Next.js scaffold & contracts.ts ready) | none | 2026-11-20 |

## Checkpoint Targets

| Checkpoint | Target Team % | Gate |
|---|---|---|
| C0 Contract freeze | – | `docs/SOURCE_OF_TRUTH.md` merged; UI mocks unblocked |
| C1 Skeleton live | 25% | Deployed web + API `/health`, auth, DB migrations |
| C2 First vertical slice | 50% | Onboarding end-to-end; `/verify` with pasted text end-to-end |
| C3 Feature complete | 85% | All P0 features live on staging |
| C4 Demo freeze | 100% | No new features; bug fixes, seed data, backup video |

## Team Summaries

_Hardhik appends checkpoint rollups and any scope-cut flags here._

```text
[TEAM] C0 | Overall 18%
Arnav 0% (Phase 1/6) | Divyansh 0% (Phase 1/6) | Hardhik 71% (Phase 4/6) | Ananya 0% (Phase 1/6)
Behind target: none (C0 contract freeze reached; next target C1 25% by Hour 8)
Blockers: docs/PRD.md export pending; live cloud secrets (Supabase, OpenRouter, Vercel/Render, GitHub remote) needed for C1 staging deploy
```

## Hardhik

_Append updates here._

```text
[Hardhik] 71% | Phase 4/6: CI & deployment
Done: C0 repo+Next.js scaffold (`make lint/typecheck/build` pass); Alembic+Postgres/SQLite+Supabase JWT `/me`; OpenRouter `core.llm`, 300/300 adversarial guardrails (0 breaches, 50/50 benign), real yfinance `core.market` (37 CSVs, `as_of=2026-11-20`), CI/Render/Docker/scripts (`55/55` pytest pass).
Next: Link GitHub remote, wire live Supabase/OpenRouter secrets, deploy staging API (Render) + Web (Vercel) for C1.
Minor: ZOMATO->ETERNAL & TATAMOTORS->TMPV mapped post-corporate-action; `db/migrations/env.py` logging fix applied; aligned `contracts.ts` & `api-client.ts` to SoT §7 and fixed `Makefile` bun/npm compatibility.
Blockers: Live Supabase/OpenRouter/Vercel/Render creds, GitHub remote URL, and `docs/PRD.md` export (need from Hardhik).
```

```text
[Hardhik] 76% | Phase 4/6: CI & deployment
Done: Linked & pushed `Rossonerian/AADHA_PS` (`main`); GitHub Actions CI run `44775028099` passed (`Web` 37s, `API` + Postgres 16 + Alembic + 55 pytest 1m5s).
Next: Wire live Supabase/OpenRouter env secrets and deploy staging API (Render/Railway) + Web (Vercel) for C1.
Minor: Merged remote `PROMPT_*.md` and `SOURCE_OF_TRUTH_1.md` cleanly without rewriting history.
Blockers: Live Supabase/OpenRouter/Vercel/Render creds and `docs/PRD.md` export (need from Hardhik).
```

```text
[Hardhik] 80% | Phase 4/6: CI & deployment
Done: Provisioned Neon (`dawn-silence-66045214`), live Alembic (`0001_initial_platform`), wired Next 16 + Neon SDKs (`@neon/auth`, `files-sdk`, `@neon/realtime`, `pg`) & FastAPI EdDSA JWKS; live E2E proved Postgres, Auth (`/api/v1/me` 401->200), Storage, Realtime; `59/59` pytest + build green.
Next: Deploy API (Render) + Web (Vercel) with Neon/OpenRouter cloud secrets for C1 staging URLs.
Minor: Updated `core.llm` default model to `nvidia/nemotron-3.5-lightning:free` ($0 fallback pricing); enabled `http://127.0.0.1:3000` in Neon Auth dev trusted origins.
Blockers: Render/Vercel deploy URLs, OPENROUTER_API_KEY in cloud, docs/PRD.md export.
```

## Arnav

_Append updates here._

## Divyansh

_Append updates here._

## Ananya

_Append updates here._
