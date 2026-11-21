# PaisaProof — Team Status

> Updated by everyone in their own section; summarised by **Hardhik** after each checkpoint.
> Progress update format and checkpoint rules: [`docs/SOURCE_OF_TRUTH.md` Section 12](docs/SOURCE_OF_TRUTH.md#12-progress-updates-all-agents).

## Team Summary

| Person | % | Phase | Blockers | Last Update |
|---|---|---|---|---|
| Hardhik | 92% | Phase 6/6 (PR #10 synced with main PRs #9/#11/#12/#13; Neon re-seeded with PR #11 real-data Education content; awaiting PR #10 merge & 2x live smoke) | PR #10 merge + Arnav 3 MAJOR decisions; OpenRouter quota / 2x live /verify smoke; `/api/neon/health` 403 in `apps/web/`; Render `FINNHUB_API_KEY`, cron confirm & service rename; Vercel project title; `docs/PRD.md` & C4 backup video | 2026-11-21 |
| Arnav | 80% | Phase 6/6 (PR #9 & PR #13 merged onto main: 30x5 real seed, durable Nasdaq challenges, unified TOOL_LOCKED, 503 guard, top-level data_origin) | Live F1 (OpenRouter quota + held-out set); production Verifier real-seed load & SoT quota decision; vetted deletion evidence | 2026-11-21 |
| Divyansh | 100% | Phase 6/6 (PR #11 merged — Education real-data provenance & Nasdaq gate hardened) | none | 2026-11-21 |
| Ananya | ~90% (PR #12 merged & live on Vercel) | Phase 6/6 (v0 UI live: demo workspace removed, Neon Auth tabs, dev-only mocks, Looseleaf polish) | `/api/neon/health` 403 prod guard in `apps/web/`; mobile nav confirmation | 2026-11-21 |

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

```text
[TEAM] C1 | Overall 39%
Arnav 76.25% (Phase 3/6 & 6/6) | Divyansh 0% (Phase 1/6) | Hardhik 80% (Phase 6/6) | Ananya 0% (Phase 1/6; UI PRs #2/#3 merged, % self-update pending)
Behind target: Divyansh (target C1 25%; next target C2 50%) — prioritize P0 onboarding, plan, and lessons before P1/P2 polish
Blockers: docs/PRD.md export pending; Arnav live F1 & real-source Option A/B sign-off; Divyansh education backend routes for C2
```

```text
[TEAM] C3 (Pre-Freeze) | Overall ~84% (est. — owner self-updates requested)
Arnav 76.25% (Phase 3/6 & 6/6; please self-update) | Divyansh 100% (Phase 6/6; please confirm after main integration) | Hardhik 85% (Phase 6/6) | Ananya ~75% est. (PRs #2,#3,#6,#7,#8 merged; please self-update)
Behind target: Arnav 76.25% vs C3 85% (live extraction F1 blocked on OpenRouter quota + Phase 6 real-source Option A/B sign-off); Ananya UI unverified with mocks=false
Blockers: OpenRouter free daily limit exhausted (53/50, $0 credits); Vercel NEXT_PUBLIC_USE_MOCKS=false & Render FINNHUB_API_KEY/cron confirm; docs/PRD.md export & C4 backup video
```

```text
[TEAM] Pre-Judging Audit | Overall ~85% (est. — Ananya self-update requested)
Arnav 76.25% (PR #9 open) | Divyansh 100% | Hardhik 90% (PR #10 open) | Ananya ~75% est. (PRs #2,#3,#6,#7,#8 merged on main)
Behind target: Arnav 76.25% vs C3 85% (live F1 blocked on OpenRouter quota + Phase 6 real-source Option A/B); Ananya UI mocks-off & `/api/neon/health` 403 not yet on main (`5f4a89d`)
Blockers: OpenRouter free daily limit exhausted (53/50, 0 remaining); Vercel `NEXT_PUBLIC_USE_MOCKS=false` + project title; Render dashboard `FINNHUB_API_KEY` + cron schedule confirm + service name; remaining `Aacharya` strings in `education/` & `nasdaq_verifier/`; `docs/PRD.md` export & C4 backup video
```

```text
[TEAM] Pre-Judging Rollup (Post-PR #9/#11/#12/#13) | Overall ~91%
Arnav 80% (PR #9 & PR #13 merged on main) | Divyansh 100% (PR #11 merged on main) | Hardhik 92% (PR #10 synced & CI-ready) | Ananya ~90% (PR #12 merged & live on Vercel)
Behind target: Final C4 demo freeze pending PR #10 merge, 2x live staging smoke, and dashboard/docs completion
Blockers: PR #10 review/merge; Arnav 3 MAJOR decisions (SoT public-research seed policy, 61 default-horizon quota, OpenRouter quota + held-out F1 set); 2x live staging smoke; `/api/neon/health` 403 prod guard in `apps/web/`; Render `FINNHUB_API_KEY`, cron confirm & service rename; Vercel project title; `docs/PRD.md` export & C4 backup video
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
Done: Provisioned Neon (Lakebase Postgres, Auth, Storage, Realtime), live Alembic (`0001_initial_platform`), wired Next 16 + Neon SDKs (`@neon/auth`, `files-sdk`, `@neon/realtime`, `pg`) & FastAPI EdDSA JWKS; live E2E proved Postgres, Auth (`/api/v1/me` 401->200), Storage, Realtime; `59/59` pytest + build green.
Next: Deploy API (Render) + Web (Vercel) with Neon/OpenRouter cloud secrets for C1 staging URLs.
Minor: Updated `core.llm` default model to `nvidia/nemotron-3.5-lightning:free` ($0 fallback pricing); enabled `http://127.0.0.1:3000` in Neon Auth dev trusted origins.
Blockers: Render/Vercel deploy URLs, OPENROUTER_API_KEY in cloud, docs/PRD.md export.
```

```text
[Hardhik] 80% | Phase 4/6: CI & deployment (complete -> entering Phase 6/6)
Done: Live C1 verified end-to-end across Vercel (https://aadha-ps.vercel.app), Render API, and Neon (Postgres, Auth, Object Storage, Realtime); CORS preflight 200, /api/neon/health 200 (all 4 services ok), Vercel Auth -> EdDSA JWT -> Render /api/v1/me (401->200), POST /api/v1/verify 200 & GET /api/v1/submissions/mine 200, `daily_job.py` executed against live Neon Postgres and logged in `job_runs`, CI & 286/286 pytest green.
Next: Checkpoint C2/C3 integration with Divyansh education routes & Ananya live UI wiring, update data/DATA_MANIFEST.md, and run full staging smoke test twice before C4.
Minor: Disabled reasoning token overhead for Nemotron models in core.llm so structured outputs do not truncate; guarded /api/neon/verify with 403 in production, hardened CORS/base-URL normalization, and cleaned up README.md and Makefile check commands.
Blockers: docs/PRD.md export; Divyansh education endpoints for full C2/C3 smoke path.
```

```text
[Hardhik] 85% | Phase 6/6: Staging hardening, content seeding & fresh-user smoke harness
Done:
- Added sliding-window per-user (20/min) & per-IP (60/min) 429 rate limiting, 413 payload caps (1 MiB / 10 MiB /verify, Content-Length & streamed), and /health stale-market warning (`market_data_stale`).
- Updated `infra/scripts/seed.py` to load Education content tables only (live Neon DB verified: questions=120, lessons=12, scenarios=24, edu_explain_cache=30, users=0); updated `README.md`, `.env.example`, and `data/DATA_MANIFEST.md` (zero leaked secrets; zero edits in apps/web/).
- Extended `infra/scripts/smoke_test.py` (`--fresh-user --cleanup-db --max-stale-days` across onboarding -> plan -> lesson -> scenario -> explain -> verify -> dashboard); live staging run passed Steps 1-7 (`health`, `/me`, 12-Q `onboarding`, `plan/lesson`, `scenarios`, `explain`) then hit OpenRouter 429 at `/verify`; offline full walkthrough passes in pytest.
- Local verification output:
  `pytest services/api/tests -q`: `312 passed, 1 warning in 23.84s`
  `ruff check services/api infra db/migrations`: `All checks passed!`
  `black --check services/api infra db/migrations`: `91 files would be left unchanged.`
  `mypy services/api/app`: `Success: no issues found in 58 source files`
Next: Re-run `infra/scripts/smoke_test.py --fresh-user --cleanup-db` twice on staging once OpenRouter quota & Vercel `NEXT_PUBLIC_USE_MOCKS=false` are resolved, complete `docs/DEMO_BACKUP_CHECKLIST.md`, and freeze C4.
Minor: Branch `infra/staging-hardening` opened via PR (not self-merged); verified live Vercel `/api/neon/verify` returns 403 (`https://aadha-ps.vercel.app`) while `/api/neon/health` currently returns 200 and live bundle still compiles `NEXT_PUBLIC_USE_MOCKS !== "false"`.
Blockers: OpenRouter free-models-per-day quota exhausted (53/50, $0 credits); Vercel `NEXT_PUBLIC_USE_MOCKS=false` & Render `FINNHUB_API_KEY`/cron check; Ananya `apps/web/.env.example` & `/api/neon/health` 403 decision; `docs/PRD.md` export & C4 video.
```

```text
[Hardhik] 90% | Phase 6/6: Pre-judging audit fixes & L3->L4 assessment smoke extension
Done:
- Repo hygiene & single naming: moved root `PROMPT_*.md` into `docs/team/`, removed duplicate `SOURCE_OF_TRUTH_1.md` (keeping single `docs/SOURCE_OF_TRUTH.md`), updated GitHub repo description to `PaisaProof — Indian retail investor literacy and financial claim verification platform`, and renamed CI database `aacharya_test` -> `paisaproof_test` in `.github/workflows/ci.yml` (`infra/render.yaml` & `infra/docker-compose.yml` already use `paisaproof*`).
- Blueprint, docs & checklist sync: added `FINNHUB_API_KEY`, `MARKET_DATA_MAX_STALE_DAYS`, `RATE_LIMIT_*`, and `MAX_*_BODY_BYTES` to `infra/render.yaml` (`paisaproof-api`); updated `README.md` (assessment step in smoke command + dev-only `/api/neon/*` 403 note) and `docs/DEMO_BACKUP_CHECKLIST.md` (level-up assessment checkbox + fresh Neon Auth sign-up note); scrubbed Neon project ID from `STATUS.md`.
- Extended `infra/scripts/smoke_test.py` (calibrated onboarding `conf=55` -> L3, added `POST /assessments/{level}/start` + `POST /assessments/{id}/submit` -> L4 promotion, then `scenarios` -> `explain` -> `verify` -> `dashboard` at L4) and updated `test_smoke_test_full_walkthrough_against_asgi_app`.
- Observed staging & DB verification: Render `/health` `{"status":"ok","version":"0.1.0","db":"ok","market_data_as_of":"2026-11-20"}`; CORS preflight (`Origin: https://aadha-ps.vercel.app`) `200`; Neon Postgres `users=0`, `questions=120`, `lessons=12`, `scenarios=24`, `edu_explain_cache=30`, `job_runs` includes `daily_job` (`id=6`, `status=ok`, `market_data_as_of=2026-11-20`). Live `smoke_test.py --fresh-user --cleanup-db` cleared steps 1–8 (`health`, `/me`, fresh Neon Auth sign-up, `onboarding`, `plan_and_lesson`, `assessment`, `scenarios`, `explain`) and exited `1` at step 9 (`POST /verify`) with `{"status": "error", "error": "POST /verify failed with HTTP 502: ... Rate limit exceeded: free-models-per-day ..."}`; `--cleanup-db` restored `public.users=0` and `neon_auth.user=0`.
- Python 3.11 verification output:
  `PYTHONPATH=services/api pytest services/api/tests -q`: `312 passed, 1 warning in 19.29s`
  `ruff check services/api infra db/migrations`: `All checks passed!`
  `black --check services/api infra db/migrations`: `91 files would be left unchanged.`
  `mypy services/api/app`: `Success: no issues found in 58 source files`
Next: Re-run `infra/scripts/smoke_test.py --fresh-user --cleanup-db` twice from clean sessions once OpenRouter quota is restored, verify Vercel/Render dashboard items & Ananya's mocks-off PR on `main`, and record C4 backup video.
Minor: Repo name decision: keep `AADHA_PS` until after judging so live Vercel/Render GitHub hooks and teammate PR remotes are not disrupted (`infra/render.yaml` & `docker-compose.yml` use `paisaproof-*`). Live Vercel (`https://aadha-ps.vercel.app`) currently returns `403` on POST `/api/neon/verify`, `200` on `/api/neon/health`, and still compiles `"false"!==env.NEXT_PUBLIC_USE_MOCKS` (serving `"Explore the demo workspace"`; `apps/web/.env.example` on `main` `5f4a89d` still has `NEXT_PUBLIC_USE_MOCKS=true`). Remaining `Aacharya` strings outside Hardhik scope noted for owners: `data/seed/education/lessons.yaml`, `data/seed/education/questions.yaml`, `services/api/app/education/{__init__.py,models.py,scripts/export_evidence.py}` (Divyansh), and `services/api/app/nasdaq_verifier/service.py` (Arnav).
Blockers: OpenRouter free-models-per-day quota exhausted (`used: 53, limit: 50, remaining: 0`); Vercel dashboard `NEXT_PUBLIC_USE_MOCKS=false` + project title; Render dashboard `FINNHUB_API_KEY`, `paisaproof-daily-cron` schedule confirm & service rename; Ananya `apps/web/` mocks-off & `/api/neon/health` 403 PR on `main`; `docs/PRD.md` export & C4 backup video.
```

```text
[Hardhik] 92% | Phase 6/6: Main integration (PRs #9-#13), live Neon real-data re-seed & rate-limit test fix
Done:
- Synced `infra/staging-hardening` (PR #10) with `origin/main` (`a12dea6`, incorporating PR #9, #11, #12, #13) with zero boundary edits (`apps/web/`, `education/`, `verifier/` untouched): kept `paisaproof_test` for `POSTGRES_DB`, `DATABASE_URL`, and `VERIFIER_POSTGRES_TEST_URL` in `.github/workflows/ci.yml`, combined `413 PAYLOAD_TOO_LARGE` + `/verify` validation redaction in `services/api/app/core/errors.py`, and merged `data/DATA_MANIFEST.md` + `STATUS.md`.
- Resolved test-harness collision with PR #9's 401-iteration `test_adversarial_100_and_en_hinglish_300_submit_never_echo_or_store` by defaulting `RATE_LIMIT_ENABLED="false"` inside `conftest.py::migrated_db` while enabling `RATE_LIMIT_ENABLED="true"` explicitly in `services/api/tests/test_rate_limit.py::_make_client_with_env` (production/dev default stays `true`).
- Re-seeded live Neon Postgres content tables via `infra/scripts/seed.py`: `files_validated=162`, `records_validated=71551`, `data_origins=["real", "synthetic"]`, `questions=120`, `lessons=12`, `scenarios=24` (`real=19`, `synthetic=5`), `edu_explain_cache=30` (`real=24`, `synthetic=6`), `0` `Aacharya` strings remaining in `lessons`/`questions`, `job_runs` recorded (`id=8`, `job_name="seed"`, `status="ok"`, `market_data_as_of="2026-11-20"`), `alembic_version=20261121_submission_owner_fk`, `public.users=1` and `neon_auth."user"=1` (existing user untouched).
- Verified live staging endpoints post-PR-#12: Vercel (`https://aadha-ps.vercel.app`) returns HTTP `200` (`has_demo_workspace=False`, `has_sign_up=True`), `POST /api/neon/verify` returns `403`, `GET /api/neon/health` returns `200`; Render `/api/v1/health` returns `{"status": "ok", "version": "0.1.0", "db": "ok", "market_data_as_of": "2026-11-20"}` with CORS preflight `200`.
- Python 3.11 verification output:
  `PYTHONPATH=services/api services/api/.venv/bin/pytest services/api/tests -q`: `352 passed, 6 skipped, 1 warning in 42.03s` (6 Postgres tests in `test_verifier_persistence.py` skip locally when `VERIFIER_POSTGRES_TEST_URL` is unset and run in CI Postgres 16)
  `services/api/.venv/bin/ruff check services/api infra db/migrations`: `All checks passed!`
  `services/api/.venv/bin/black --check services/api infra db/migrations`: `107 files would be left unchanged.`
  `PYTHONPATH=services/api services/api/.venv/bin/mypy services/api/app`: `Success: no issues found in 62 source files`
Next: Await PR #10 merge + Hardhik sign-off on Arnav's 3 MAJORs, load PR #9 real verifier seed into production Neon DB once approved, re-run `infra/scripts/smoke_test.py --fresh-user --cleanup-db` twice on staging after OpenRouter quota resets/is funded, and complete C4 docs/video.
Minor: PR #12 already merged the UI mocks-off fix (`apps/web/.env.example` `NEXT_PUBLIC_USE_MOCKS=false`) and cleaned up `Aacharya -> PaisaProof` in Education/Nasdaq files onto `main`; live OpenRouter key check prior to `00:00 UTC` (`05:30 IST`) showed `used: 53, limit: 50, remaining: 0` (needs fresh post-reset check before double smoke run).
Blockers: PR #10 review/merge; Arnav 3 MAJOR decisions; live 2x full staging smoke; `/api/neon/health` 403 prod guard in `apps/web/`; Render dashboard `FINNHUB_API_KEY`, `paisaproof-daily-cron` schedule confirm & service rename; Vercel project title; `docs/PRD.md` export & C4 backup video.
```

```text
[Hardhik] MAJOR | C4 freeze awaiting PR #10 merge, 2x live smoke, and dashboard/frontend hardening items
Impact: 2x live full-walkthrough staging certification (`health -> me -> onboarding -> lesson -> assessment -> scenario -> explain -> verify -> dashboard`) has not yet completed cleanly end-to-end; live `/api/neon/health` on Vercel still returns HTTP `200` (`apps/web/` outside Hardhik's write boundary); Render `FINNHUB_API_KEY`, `paisaproof-daily-cron` schedule provisioning, and PR #9 real-seed production loading remain open pending Hardhik sign-off.
Options: A) Merge PR #10, sign off on Arnav's 3 MAJORs (load 30×5 real Verifier seed if approved), add `/api/neon/health` 403 prod guard in `apps/web/`, confirm Render env/cron/service name & Vercel project title, verify OpenRouter quota and run `smoke_test.py --fresh-user --cleanup-db` twice, then export `docs/PRD.md` + record C4 video (recommended); B) Keep remaining open audit items explicitly documented for judging.
Need from: Hardhik/User (PR #10 merge & PR #9 policy decisions, OpenRouter quota check, Vercel/Render dashboard confirmations, `docs/PRD.md`, C4 backup video) and Ananya (`/api/neon/health` 403 guard & mobile nav confirmation in `apps/web/`).
```

## Arnav

```text
[Verifier v2] 10% | Phase 1/8: Docs and contracts complete (2026-11-21)
Done: Read approved design; branched feat/verifier-v2 from origin/main ebede08. Prior PRs #9 and #13 are already merged by others. Verified SoT copies match and all eight fact codes are documented; added API types and provider placeholders. No doc describes a displayed per-tip reliability score.
Next: Complete migration/Postgres and full acceptance checks for the implemented backend phases.
Minor: Preserve current eligibility; YouTube channel/date alone does not establish authorship of every spoken claim. Design's multi-claim assumption requires removing the existing unique claims.submission_id constraint.
Blockers: none for v2 implementation; existing seed/F1 acceptance remains open.
```

```text
[Verifier v2] MAJOR | Prior real-seed audit found a missed stated horizon
Impact: LKP SONACOMS report dated 2024-01-24 visibly states 12 M Price Target, but the shipped seed defaults to 20 sessions. The existing 61-default count is not independently accepted; horizon review/re-scoring remains required before seed sign-off.
Options: Correct and re-score frozen publication membership in a separate seed fix; do not reselect by outcome (recommended).
Need from: Arnav/Hardhik — review separate seed correction. V2 does not silently claim seed acceptance.
```


_Append updates here._

```text
[Verifier v2] 100% | Phase 8/8: Backend implementation and acceptance complete (2026-11-21)
Done: All eight implementation phases passed their gates. Python 3.11.16 full local suite: 398 passed, 1 warning, zero skips/errors; Ruff/Black/mypy green. CI run 44850097125 passed API (Postgres 16 migrations and all 398 tests) and Web (lint, formatting, types, build). PR #16: https://github.com/Rossonerian/AADHA_PS/pull/16. Only contracts.ts changed under apps/web; no Education implementation changes. SoT copies match. No production migration or production seed write.
Next: Hardhik reviews core/transcribe.py, core/web_search.py, config and migration on PR #16; UI owner can render the additive contracts. Configure Gemini/Exa keys before enabling provider calls. Leave PR unmerged.
Minor: This is implementation completion, not empirical quality/F1 acceptance. Actual quality validation correctly REFUSEs 150 eligible claims / 30 providers / 0 quality-covered claims. TIP_QUALITY_WEIGHT remains 0. Local Postgres is 18.7; Postgres 16 was verified in CI. Web lint has ten existing warnings; the single Python warning is the existing Starlette/httpx deprecation. Managed-Postgres teardown initially lost an idle connection; pool_pre_ping and confirmed disposable cleanup fixed it, followed by a fully green rerun. Raw Windows Prettier warnings are CRLF checkout differences; LF-normalized checks and Linux CI pass without rewriting UI files.
Blockers: none for v2 implementation acceptance. Core review/deployment credentials and the separate v0 real-seed/F1 decisions remain outstanding; no validated predictive claim or automatic weight activation is asserted.
```

### Verifier v2 API checks — real command output

Python 3.11.16. The local pytest run sets APP_ENV=test and VERIFIER_POSTGRES_TEST_URL to the configured database; every database test migrates only a new private disposable schema. Provider keys are blank in the test process; provider HTTP is mocked by tests. All seven Postgres variants executed, with zero skips.

```text
$ PYTHONPATH=services/api .venv/Scripts/python.exe -m pytest services/api/tests -q
398 passed, 1 warning in 168.06s (0:02:48)
$ .venv/Scripts/python.exe -m ruff check services/api infra db/migrations
All checks passed!
$ .venv/Scripts/python.exe -m black --check services/api infra db/migrations
All done!
116 files would be left unchanged.
$ PYTHONPATH=services/api .venv/Scripts/python.exe -m mypy services/api/app
Success: no issues found in 66 source files
$ git diff --check
(no output; exit 0)
```

### Verifier v2 migration checks

SQLite (FKs enabled) and Postgres upgrade -> downgrade -1 -> upgrade head pass. The migration refuses to discard multi-claim data on downgrade. Historical revision tests use reflected/stable columns at the revision being tested rather than querying future ORM columns. Production schema/migrations were untouched. Local server: `Postgres 18.7 (84da7d8)`; CI container: `postgres:16-alpine`.

[CI evidence](https://github.com/Rossonerian/AADHA_PS/actions/runs/44850097125):

```text
API (Lint, Typecheck, Migrate, Test): success
All checks passed!
116 files would be left unchanged.
Success: no issues found in 66 source files
398 passed, 1 warning in 87.34s (0:01:27)
Web (Lint, Format, Typecheck, Build): success
```

The existing frozen real seed was loaded twice at the v2 migration head in a new disposable schema, then that schema was dropped:

```text
$ PYTHONPATH=services/api .venv/Scripts/python.exe infra/scripts/load_real_verifier_seed.py --load
{"status": "loaded", "data_origin": "real", "sources": 30, "claims": 150, "min_scored_claims": 5}
$ PYTHONPATH=services/api .venv/Scripts/python.exe infra/scripts/load_real_verifier_seed.py --load
{"status": "loaded", "data_origin": "real", "sources": 30, "claims": 150, "min_scored_claims": 5}
```

This checks migration/import compatibility, not the separate unresolved horizon/provenance acceptance noted below.

### Verifier v2 web checks

`npm ci`: 645 packages added, zero vulnerabilities. `npm run lint`: zero errors, ten existing warnings. `npm run typecheck`: exit 0. `npm run build` with the same placeholder public/Auth settings as CI:

```text
Compiled successfully in 3.1s
Finished TypeScript in 7.5s
Generating static pages using 8 workers (4/4)
```

Raw `npm run format:check` flags 115 CRLF checkout files. Checking all 117 tracked web files with the same Prettier config after LF normalization in memory returns `failed: []`, `files_modified: 0`; Linux CI formatting passes. No UI source was reformatted.

### Verifier v2 offline validation checks

Synthetic fixtures exercise REFUSE, PASS, FAIL, timestamp ties, calibration buckets and provider confounding. The CLI's database access is read-only and never changes weights/scores. Actual disposable-seed output (exit 2, expected refusal):

```json
{
  "claims": 0,
  "providers": 0,
  "version": "tip-quality-v1",
  "weight_changed": false,
  "status": "REFUSE",
  "reason": "Requires >=300 eligible scored claims and >=30 providers",
  "rating_eligible_scored_claims": 150,
  "rating_eligible_providers": 30,
  "quality_covered_claims": 0
}
```

No actual-data AUC or quality acceptance PASS is claimed. An independent quality-labelled outcome corpus is still needed before considering a manual nonzero weight.

```text
[Verifier v2] MAJOR | Prior v0 live extraction F1 remains unmeasured after the latest retry
Impact: The latest live retry completed 58 structured calls before ExternalServiceError; no complete 150-row F1 exists. Previous attempts confirmed daily HTTP 429, but this retry's safe runner reports only the exception type. eval.jsonl has already supplied grounding-development feedback and is diagnostic only.
Options: Build an independent, frozen acceptance set and evaluate after quota/paid-model access is available; do not tune further on eval.jsonl (recommended).
Need from: Hardhik/Arnav — independent acceptance corpus and provider quota decision. This remains separate from the completed v2 implementation gates.
```


```text
[Verifier v2] 85% | Phase 8/8: Full acceptance and PR review in progress (2026-11-21)
Done: Phase 1 contracts mirrored; Phases 3–7 implemented and exercised (provider HTTP success/timeout/429/bad payload, caption fallback, grounded multi-claim storage, chunk-edge omission guard, historical facts and no-lookahead, API score privacy, golden weight-zero ratings, exact SEBI matching, display-only mentions, offline validation refuse/pass/fail). Targeted run: 60 passed, 7 skipped, 1 warning in 4.97s (Postgres variants intentionally absent in that invocation). Ruff passes; Black leaves 116 files unchanged; mypy checks 66 files. SQLite migration up/down/up passes with FK enforcement enabled, including refusal to downgrade multi-claim data.
Next: Finish local isolated-Postgres full suite and CI Postgres 16 round-trips, publish PR, paste final output. Phase 2's Postgres 16 gate is pending CI, so the 85% excludes that 10% and the final 5% gate.
Minor: Local Postgres is 18.7, not 16. Web lint/typecheck/build pass after npm ci; lint has 10 existing warnings. Windows CRLF checkout causes raw Prettier check warnings; all 117 tracked web files pass after LF normalization in memory (zero file writes). Only contracts.ts changed under apps/web. Gemini and Exa require deployment keys; Hardhik must review core modules. Unknown nominal/adjusted compatibility leaves quoted-price comparison facts null.
Blockers: none for implementation; CI/local full gate pending. Prior v0 seed/F1 and quota decisions remain separate acceptance blockers below.
```


```text
[Arnav] 80% | Verifier audit fixes (items 1–3 on PR #13; items 4–7 merged in PR #9) (2026-11-21)
Done: Fixed audit items 1–3 off main: (1) GET /sources/{id} below Level 3 now returns standard 403 {"error": {"code": "TOOL_LOCKED", "message": ..., "required_level": 3}}; (2) POST /verify without OPENROUTER_API_KEY now catches ConfigurationError and returns user-safe 503 {"error": {"code": "VERIFIER_UNAVAILABLE", "message": ...}} without leaking env vars or tracebacks; (3) added top-level data_origin to GET /sources/{id} and GET /submissions/mine while keeping red_flags[].evidence as an object, and updated docs/SOURCE_OF_TRUTH.md §7. Audit items 4 (Postgres Nasdaq challenge persistence + fail-closed gate + 503 FINNHUB_UNAVAILABLE), 5 (live F1 runner + quota blocker/held-out MAJOR), 6 (30×5 real public-research seed + DATA_MANIFEST), and 7 (submissions.user_id -> users.id FK migration) are merged in PR #9. No apps/web/ edits.
Next: Await Hardhik review/merge of PR #13 (and decisions on 61 default-horizon claims and OpenRouter quota / held-out F1 set).
Minor: docs/SOURCE_OF_TRUTH.md §7 updated for the unified error envelope, 503 VERIFIER_UNAVAILABLE, top-level data_origin, and red_flags[].evidence object shape (pending Hardhik approval).
Blockers: Live extraction F1 remains blocked on OpenRouter daily quota + held-out set decision.

$ PYTHONPATH=services/api .venv/Scripts/python.exe -m pytest services/api/tests -q
316 passed, 1 warning in 49.15s
$ .venv/Scripts/python.exe -m ruff check services/api infra db/migrations
All checks passed!
$ .venv/Scripts/python.exe -m black --check services/api infra db/migrations
All done! ✨ 🍰 ✨
90 files would be left unchanged.
$ PYTHONPATH=services/api .venv/Scripts/python.exe -m mypy services/api/app
Success: no issues found in 58 source files
```

```text
[Arnav] 76.25% | Phase 6/6: Real-source seed verification & PR #9 update (2026-11-21)
Done: Validated 30-publisher × 5-claim real seed (150 claims, 2023-01-12 to 2025-11-17, core.market prices cut off 2026-11-20); 150/150 public PDF HTTP 200 + SHA256 verified; idempotent --load passed on disposable Postgres schema at Alembic head 20261121_submission_owner_fk (30 sources, 150 submissions, 150 claims, data_origin=real; production DB untouched). Spot-checked 10 random claims across 10 publishers against fetched PDFs (10/10 matched publisher, date, security, direction, price levels). Confirmed 0 analyst emails/phones, max excerpt 42 chars, no report bodies, data/market_cache/ gitignored. Re-ran evaluate_extraction.py: OpenRouter daily quota still exhausted (0 calls, ExternalServiceError). Deletion evidence remains empty (missing evidence = no finding). All 342 pytest (zero skips, including 6 isolated Postgres + 9 real_seed tests), ruff, black, and mypy passed on Python 3.11.16.
Next: Await Hardhik review/decisions on the 3 MAJORs below (SoT seed policy, 61 default-horizon claims, OpenRouter quota + independent held-out set); leave PR #9 unmerged and production migrations unapplied.
Minor: Kept SOURCE_OF_TRUTH.md diff strictly to the 13-line proposed public-research seed policy; updated DATA_MANIFEST.md, docs/evidence/real_source_seed.md, and docs/evidence/extraction_f1.md; no apps/web/ edits.
Blockers: 3 MAJORs below (SoT contract change, default-horizon quota decision, OpenRouter quota + held-out acceptance set); vetted deletion evidence still absent.

$ PYTHONPATH=services/api .venv/Scripts/python.exe infra/scripts/load_real_verifier_seed.py
{"status": "validated", "claims": 150}
$ PYTHONPATH=services/api .venv/Scripts/python.exe infra/scripts/load_real_verifier_seed.py --check-publications
{"public_pdfs_verified": 150, "digest_matches": 150}
$ PYTHONPATH=services/api .venv/Scripts/python.exe -m pytest services/api/tests -q
342 passed, 1 warning in 145.88s (0:02:25)
$ .venv/Scripts/python.exe -m ruff check services/api infra db/migrations
All checks passed!
$ .venv/Scripts/python.exe -m black --check services/api infra db/migrations
All done! ✨ 🍰 ✨
104 files would be left unchanged.
$ PYTHONPATH=services/api .venv/Scripts/python.exe -m mypy services/api/app
Success: no issues found in 60 source files
```

```text
[Arnav] MAJOR | Contract change proposed in docs/SOURCE_OF_TRUTH.md for public-research seed policy (2026-11-21)
Impact: Adds 13 lines under Section 8 defining `broker_research` corporate-publisher identity (alias brands collapsed), Level-1 import owner, provenance/excerpt retention, end-of-day Asia/Kolkata storage for date-only reports, strict post-date scoring sessions, 20/252 session horizon mapping, explicit 20-session default for unstated horizons, benchmark-relative scoring for target-only reports, and sample-limitation disclosure. Blocks merging PR #9 until Hardhik approves.
Options: A) Approve the 13-line public-research seed policy in docs/SOURCE_OF_TRUTH.md as part of PR #9 (recommended); B) request revisions to the contract before merge.
Need from: Hardhik — contract review and approval on PR #9.
```

```text
[Arnav] MAJOR | Decision needed: do the 61 default-horizon claims count toward the ">=5 scored claims" quota? (2026-11-21)
Impact: 61 of 150 real-seed claims use `horizon_basis="verifier_default_20_sessions"` (20 trading sessions) because the source PDF states no horizon (89 have explicit stated horizons). If default-horizon claims are excluded from the ">=5 scored claims per publisher" quota, 13 of 30 publishers fall short by a total of 61 claims:
  - asit_c_mehta: stated=1, default_20=4, shortfall=4
  - axis_securities: stated=0, default_20=5, shortfall=5
  - bp_wealth: stated=2, default_20=3, shortfall=3
  - elara_securities: stated=0, default_20=5, shortfall=5
  - hdfc_securities: stated=0, default_20=5, shortfall=5
  - hem_securities: stated=0, default_20=5, shortfall=5
  - idbi_capital: stated=0, default_20=5, shortfall=5
  - lkp_securities: stated=1, default_20=4, shortfall=4
  - nirmal_bang_institutional_equities: stated=0, default_20=5, shortfall=5
  - nuvama: stated=0, default_20=5, shortfall=5
  - prabhudas_lilladher: stated=0, default_20=5, shortfall=5
  - religare: stated=0, default_20=5, shortfall=5
  - sharekhan: stated=0, default_20=5, shortfall=5
Options: A) Count the 61 explicitly labelled 20-session-default claims toward the 30×5 quota, retaining their `verifier_default_20_sessions` disclosure (recommended, matches existing Verifier extraction default); B) require stated horizons on all 150 claims and collect 61 replacement stated-horizon reports across the 13 publishers above.
Need from: Hardhik — quota policy decision.
```

```text
[Arnav] MAJOR | Live extraction F1 still blocked by OpenRouter quota; independent held-out set needed (2026-11-21)
Impact: Re-running `infra/scripts/evaluate_extraction.py` hit `ExternalServiceError` immediately (0 calls; OpenRouter free-tier daily quota has not reset), so live F1 remains unmeasured (`null`). In addition, `data/seed/verifier/eval.jsonl` was used during earlier grounding recall work and is no longer a held-out acceptance set.
Options: A) Once quota resets or a paid OpenRouter model is configured, run `evaluate_extraction.py` on `eval.jsonl` strictly as a diagnostic (no further tuning on `eval.jsonl`) and build a fresh independent held-out acceptance set for formal F1>=0.80 sign-off (recommended); B) explicitly accept a diagnostic-only `eval.jsonl` run once quota is available.
Need from: Hardhik — OpenRouter quota/paid-model approval and sign-off on building an independent held-out acceptance set.
```

```text
[Arnav] 76.25% | Nasdaq / Platform / Privacy hardening (2026-11-21)
Done: Durable owner-scoped 30-minute challenge keys; fresh-process restart, one-winner concurrent submit, TTL and JSON-plan gate tests. Owner-FK revision up/down/re-up passed on isolated Postgres with existing submission preserved. Live Finnhub quote/profile/metrics 200, candles 403 -> empty chart; 4 real-data questions. Bound 2,245 official AMFI categories and reviewed-deletion provider; 100 + 300 EN/Hinglish adversarial cases exercised on each endpoint, phones redacted before hashing. 333 tests passed.
Next: Review PR #9 and apply its migrations after approval; finish live F1 and real-source quota.
Minor: SOURCE_OF_TRUTH.md proposes persistence, exact-answer and origin details for review; no apps/web edits. Production DB was read only; migrations tested in disposable schemas. See docs/evidence/verifier_hardening.md.
Blockers: Real-data acceptance remains open (MAJOR below). No synthetic-only approval assumed.

$ PYTHONPATH=services/api python -m pytest services/api/tests -q
333 passed, 1 warning in 285.01s (0:04:45)
$ python -m ruff check services/api infra db/migrations
All checks passed!
$ python -m black --check services/api infra db/migrations
All done! ✨ 🍰 ✨
98 files would be left unchanged.
$ python -m mypy services/api/app
Success: no issues found in 59 source files
```

Python 3.11.16 (`.venv/Scripts/python.exe`); the full pytest run used
`VERIFIER_POSTGRES_TEST_URL` loaded privately from local settings, with the
application `DATABASE_URL=sqlite://`, `DATABASE_URL_UNPOOLED=""`, `APP_ENV=test`.
All 6 Postgres persistence cases ran (no skipped tests). Warning: Starlette's
`httpx` TestClient deprecation. No API key or database URL was printed.

```text
[Arnav] MAJOR | Real-data acceptance gates remain open (2026-11-21)
Impact: Read-only Postgres count is 0 qualifying public real sources (need >=30 with >=5 scored claims each). F1 remains unmeasured after OpenRouter daily quota; eval.jsonl also has prior development feedback. No vetted real deletion notice/capture pair is available, so no deletion finding is asserted.
Options: A) Source and independently vet the required public dated claims, complete live F1 with enough quota and resolve held-out integrity (recommended); B) synthetic-only remains NOT approved — user explicitly chose to keep the real-data gate open.
Need from: Hardhik/Arnav — verified public-source corpus and deletion provenance; OpenRouter quota and evaluation-integrity decision. Finnhub key now works. PR #9 is reviewable but not merged or deployed.
```

```text
[Arnav] MAJOR | Live F1 retry blocked by OpenRouter daily quota (2026-11-21)
Impact: Key loads after copying .env.txt to ignored .env; 41 real structured calls completed before ExternalServiceError. Diagnostic confirmed HTTP 429 with a daily-limit message. Full F1 remains unmeasured.
Options: A) Hardhik provides enough OpenRouter quota for all 150 rows (recommended); B) wait for quota reset, then rerun without tuning. Existing corpus independence issue remains open.
Need from: Hardhik — sufficient quota and held-out evaluation decision. Raw summary saved in docs/evidence/extraction_f1.md. FINNHUB_API_KEY still absent; Postgres URL now configured but not exercised. Tasks 2–6 pending per stop rule.
```

```text
[Arnav] MAJOR | First real test blocked at Step 1 (2026-11-21)
Impact: OPENROUTER_API_KEY is absent; live exact-match F1 is unmeasured, not zero. Existing grounding updates below report development against eval.jsonl, compromising its held-out status.
Options: A) Hardhik configures OpenRouter and supplies an independent held-out acceptance set (recommended); B) explicitly accept the existing corpus as a diagnostic only. No tuning performed in this run.
Need from: Hardhik — OpenRouter access and evaluation-integrity decision. Tasks 2–6 remain pending under the requested stop-on-blocker rule; no synthetic-only sign-off assumed.
```

```text
[Arnav] 76.25% | Phase 3/6: First real-test preflight
Done: Added real-core evaluation runner and raw blocked output in docs/evidence/extraction_f1.md; Python 3.11.16 validation below.
Next: Configure OpenRouter and resolve held-out integrity, then resume the ordered task list.
Minor: FINNHUB_API_KEY absent; configured DB is SQLite. No apps/web edits or contract changes.
Blockers: Live F1 unmeasured; no acceptance progress claimed.

$ PYTHONPATH=services/api python -m pytest services/api/tests -q
306 passed, 1 warning in 31.37s
$ python -m ruff check services/api infra db/migrations
All checks passed!
$ python -m black --check services/api infra db/migrations
All done! ✨ 🍰 ✨
90 files would be left unchanged.
$ PYTHONPATH=services/api python -m mypy services/api/app
Success: no issues found in 57 source files
```

Commands above used `.venv/Scripts/python.exe`; pytest's warning is Starlette's
deprecation of `httpx` with `starlette.testclient` in favor of `httpx2`.

```text
[Arnav] MAJOR | Platform scaffold and PRD are missing; the supplied SoT is the only available contract.
Impact: Fresh-DB migration, authenticated API integration, and live extraction and market checks are blocked.
Options: A) Hardhik provides the missing scaffold and interfaces while Orca workers build independent Verifier modules (recommended); B) pause all work.
Need from: Hardhik — PRD, users migration revision, DB/session and core bindings, and authoritative market-cap and post-deletion inputs.
```

```text
[Arnav] 7.5% | Phase 1/6: Models and migration
Done: Four-table Alembic revision upgraded, downgraded, and reapplied on fresh SQLite; 7 migration and schema tests passed.
Next: Run the revision on PostgreSQL; wire ingestion and scoring into the Verifier service.
Minor: Orca’s architecture worker recommended an independent revision root, with the users FK added at platform integration.
Blockers: Hardhik’s Alembic setup and user ID contract are still missing.
```

```text
[Arnav] 10% | Phase 1/6: Models and migration
Done: 7 tests passed against fresh PostgreSQL 17.11, including upgrade, downgrade, re-upgrade, and constraint checks.
Next: Verify ingestion and scoring together through the API.
Minor: The Verifier revision is independently runnable.
Blockers: Hardhik still needs to join the revision to the platform migration history and confirm the users FK.
```

```text
[Arnav] 30% | Phase 2/6: Ingestion
Done: 48 ingestion tests passed; offline OCR preserved a price and redacted a phone number. API tests verified deduplication and owner isolation.
Next: Exercise claim extraction and the red flags.
Minor: Provider-restricted URLs fall back to paste or screenshot; YouTube uses official publication metadata when available.
Blockers: None for local acceptance; live transcript availability is provider-dependent.
```

```text
[Arnav] MAJOR | Live extraction F1 and the real-source seed requirement cannot be verified.
Impact: Phase 3’s F1 gate and Phase 6’s mixed-origin demo gate remain open.
Options: A) Evaluate the 150 labelled messages with core.llm.complete and score vetted public tips through core.market (recommended); B) explicitly approve a synthetic-only demo.
Need from: Hardhik — runnable shared core, OpenRouter access, and vetted public tip provenance with adjusted price history.
```

```text
[Arnav] 45% | Phase 3/6: Claim extraction
Done: Orca worker verified 150 unique labelled tips (60 Hinglish; 75 scorable and 75 non-calls). Local tests cover malformed output, price grounding, and confidence.
Next: Run exact structured-match F1 against the shared extractor and resolver.
Minor: Corpus validity is not an F1 result.
Blockers: Shared LLM/market core and OpenRouter access.
```

```text
[Arnav] 45% complete | Phase 4/6: Red flags
Done: Eight red-flag tests passed; the API verified basic mode and hid rating and outcome data below Level 3.
Next: Bind production market-cap and confirmed-deletion evidence.
Minor: Missing evidence does not produce a finding.
Blockers: Production evidence providers; Phase 3 live F1 remains open.
```

```text
[Arnav] 65% complete | Phase 5/6: Scoring and ratings
Done: Deterministic scoring and rating tests passed, including split/bonus, missing data, and ambiguous barriers. API tests verified rating history, idempotence, and read endpoints.
Next: Schedule the job after the shared market refresh.
Minor: One eligible revision per public post contributes to a source rating.
Blockers: Platform scheduler and nominal/adjusted price-basis binding; Phase 3 live F1 remains open.
```

```text
[Arnav] 76.25% | Phase 6/6: Seed and demo
Done: Fresh PostgreSQL seeded 6 synthetic sources with at least 5 scored calls each; local WhatsApp-style demo took 15 ms; 100 adversarial inputs returned no directive. All 122 tests, Ruff, mypy, and compilation passed.
Next: Run live extraction F1 and load scored, provenance-backed real tips.
Minor: Demo timing and adversarial output checks used the local API test harness.
Blockers: Real-source quota not met; platform authentication/core integration and live F1 remain unverified.
```

```text
[Arnav] 76.25% | Phase 3/6: Extraction grounding and ingestion privacy
Done: Unsupported forecasts and mismatched price roles now return needs_review without claim fields. Split contact numbers are redacted before hashing, storage, and model calls. 81 focused tests, Ruff, mypy, and compilation passed.
Next: Measure exact-match extraction F1 against the live shared core.
Minor: Unsupported phrasing is deliberately sent to review; coverage is not a measured F1 result.
Blockers: Live shared core and real-source dataset remain unavailable.
```

```text
[Arnav] MAJOR | The extraction grounding check is too restrictive for the evaluation corpus.
Impact: With gold fields and the full message supplied as evidence, only 15 of 59 exact-symbol positives passed. This is not live F1, but it exposes a recall problem.
Options: A) Keep unsupported claims in review and improve safe coverage against the corpus before the live run (recommended); B) explicitly narrow the supported formats.
Need from: Hardhik — runnable shared core for the live acceptance run.
```

```text
[Arnav] 76.25% | Phase 3/6: Scoring horizon
Done: Verified relative horizons from source text even when omitted by the model; model mismatches and unsupported deadlines stay in review. 39 extraction/API tests, Ruff, mypy, and compilation passed.
Next: Improve grounding coverage and run live F1.
Minor: The default 20 sessions is not substituted for a recognized explicit deadline.
Blockers: Grounding recall, live core, and real-source seed quota.
```

```text
[Arnav] 76.25% | Phase 3/6: Grounding coverage
Done: Added support for shorthand trade cards and directional statements in English and Hinglish. 44 extraction/API tests, Ruff, mypy, and compilation passed.
Next: Validate additional supported syntax on independent examples, then measure live F1.
Minor: The same gold-field/full-message diagnostic improved from 15/59 to 29/59. This is not live F1 and remains insufficient evidence for acceptance.
Blockers: Grounding recall, live core and OpenRouter access, and the provenance-backed real-source seed.
```

```text
[Arnav] 76.25% | Phase 3/6: Price-omission guard
Done: If the model drops a target/stop/entry tied to the same forecast (e.g. evidence "INFY will rise" from "INFY will rise. Target 1600; SL 1450."), the claim now goes to needs_review. All 165 verifier tests, Ruff and mypy pass.
Next: Handoff to finish grounding recall (diagnostic 30/59), live F1, and real-source seed.
Minor: Diagnostic is not live F1.
Blockers: Live shared core + OpenRouter; provenance-backed real tips.
```

```text
[Arnav] 76.25% | Phase 3/6: Grounding recall
Done: Safe grounding recall diagnostic improved from 30/59 to 59/59 exact-symbol positives and 1/16 to 14/16 alias-symbol positives on eval.jsonl while negative direction-only passes dropped from 4 to 1 (NIFTY spot index only). Verified all 16 alias labels map cleanly via resolve_symbol. All 214 verifier tests (49 new original tests), mypy, ruff, and py_compile pass.
Next: Run live extraction F1 (>= 0.80) once shared core and OpenRouter access are available; finalize Phase 6 real-source seed or approved Option B.
Minor: Grounding diagnostic is not live F1; eval.jsonl was kept untouched as held-out evaluation set.
Blockers: Hardhik — services/api/app/core/ (llm, guardrails, market), OpenRouter key, and provenance-backed real tips (or Option B sign-off).
```

```text
[Arnav] MAJOR | Phase 3 live F1 and Phase 6 real-source seed remain blocked on missing shared core and real tip dataset
Impact: Phase 3 live F1 (>= 0.80) and Phase 6 real-source quota (30+ sources, >= 5 scored claims each, data_origin="real") cannot be completed or signed off; risks C3/C4 integration readiness.
Options: A) Hardhik provides services/api/app/core/ (llm.complete, guardrails.check_output, market), OpenRouter access, and vetted dated public tips to score deterministically against real adjusted prices (recommended if time permits); B) Hardhik explicitly approves a synthetic-only demo for Phase 6 while unblocking core.* for live F1.
Need from: Hardhik — services/api/app/core/, OpenRouter access, and Option A vs Option B decision for Phase 6.
```

```text
[Arnav] 76.25% | Phase 3/6: Merged origin/main & platform integration
Done: Merged origin/main (711fa6c) into feat/verifier-backend without losing Verifier or grounding changes; resolved STATUS.md, router.py (exports platform `router` + preserves `create_router`), and jobs.py (supports both Verifier `SessionFactory+VerifierCore` and `daily_job` `Session|None`); joined Alembic revision `20261120_verifier` onto `0001_initial_platform`; added `platform_core()` adapter and `date`-column DataFrame compatibility in `scoring.py`/`red_flags.py`. Verified 276/276 pytest (platform + Verifier), ruff, black, strict mypy, Alembic upgrade/downgrade/re-upgrade, py_compile, and 59/59 exact grounding diagnostic.
Next: Run live extraction F1 (`>= 0.80`) with `OPENROUTER_API_KEY` and finalize Phase 6 real-source dataset or Hardhik Option B approval.
Minor: Added Verifier runtime deps + `types-requests` to `services/api/pyproject.toml` and updated `test_jobs_and_seed.py` from `stub` to `ok`. `submissions.user_id -> users.id` FK remains deferred to a platform reconciliation revision so standalone owner tests stay intact.
Blockers: `OPENROUTER_API_KEY` (for live F1 evaluation) and Phase 6 real-source dataset / Option B approval from Hardhik.
```

```text
[Arnav] 76.25% | Capstone: Nasdaq literacy verifier (contract proposal, Hardhik approval needed)
Done: Added core/finnhub.py (endpoint allowlist, cache), nasdaq_verifier gate/router/service (`403 TOOL_LOCKED` unless level 4 + plan 100% + Brier <= 0.25, fails closed), `/me` unlock, tests, typed web client + `/nasdaq-verifier` UI; docs and PROMPT_* notes updated.
Next: Divyansh to populate `plans.progress` / `skill_scores.brier`; Hardhik to review the SOURCE_OF_TRUTH change and set FINNHUB_API_KEY.
Minor: NDX benchmark is served via the QQQ ETF (index quotes need a paid Finnhub plan); `/stock/candle` may be plan-restricted, so the chart degrades gracefully. Challenge answer keys are process-local.
Blockers: Live FINNHUB_API_KEY not tested; gate inputs depend on education tables that do not exist yet.
```

## Divyansh

```text
[Divyansh] 100% | Phase 6/6: Education real-data hardening and acceptance
Done: Closed the provenance and Nasdaq gate gaps; added full-suite coverage, submission replay/shape checks, answer-key exposure checks, mixed-origin evidence exports, and market-data refresh support. Changes are on `feat/education-real-data-next` and ready for PR review.
Next: Review PR into `main`; no merge performed.
Minor: Five scenarios and six Explain examples remain synthetic because Yahoo Finance lacks their historical delisted-symbol data.
Blockers: none for local acceptance.
```

```text
[Divyansh] RESOLVED | Education historical provenance and Nasdaq gate
Impact: Education records are labeled real only when complete real market history is available; missing historical/delisted symbols remain synthetic. The Nasdaq gate now reads the education JSON lesson map and skill Brier values through typed SQLAlchemy queries, and derives completed lesson percentage from the plan.
Done: Refreshed 19/24 scenario records and 24/30 Explain records from `core.market`; added fail-closed provenance checks, answer-submission validation, separate-origin evidence cohorts, and a fresh-account end-to-end test. Unavailable historical records: five scenarios and six Explain examples.
Evidence: Full suite `PYTHONPATH=services/api pytest services/api/tests -q`: 314 passed, 1 warning. Ruff: all checks passed. Black: 82 files unchanged. Mypy: no issues in 58 source files. `git diff --check` clean.
Remaining data limitation: Yahoo Finance does not provide the requested historical series for the delisted/unavailable symbols; those examples are explicitly retained as synthetic.
```

```text
[Divyansh] MAJOR | Contract gaps identified in SoT Section 7 before Phase 1 start
Impact: Blocks frontend-backend integration for lesson completion (C2) and study mode (C3); minor ambiguity on 403 TOOL_LOCKED JSON nesting and scenario direction enum.
Options: A) Add non-breaking extension endpoints (`POST /api/v1/lessons/{id}/check`, `POST /api/v1/study/start`, `POST /api/v1/study/{id}/submit`), standardize `direction` as `up|down|flat`, and include both `error: {code, message, required_level}` and top-level `code`/`required_level` on 403 TOOL_LOCKED; B) Freeze without lesson-completion/study endpoints and rely on client-side state. Recommend A.
Need from: Hardhik (contract PR approval) & Ananya (UI confirmation).
```

```text
[Divyansh] 10% | Phase 1/6: Models, Migration & Content Loader
Done:
- Implemented SQLAlchemy 2.0 models, Alembic migration (`20261120_01_education_tables.py`) + SQL DDL, and idempotent YAML loader with `data_origin` and `core.guardrails.check_output()` enforcement.
- Verified with `unittest` (`test_phase1_models_loader.py`: 3/3 passed — fresh DB upgrade/downgrade, CHECK constraints, sample YAML import & guardrail block).
Next: Phase 2 — Adaptive onboarding engine, Brier scoring, and 120-question bank across L1-L3.
Minor: Built dual SQLAlchemy 2.0 + DB-API 2.0 repository so tests run cleanly with zero external DB server.
Blockers: none
```

```text
[Divyansh] 30% | Phase 2/6: Adaptive Onboarding & Question Bank
Done:
- Authored 120 non-advisory Indian market questions in `data/seed/education/questions.yaml` (>= 10 per skill area per level across L1-L3).
- Implemented adaptive staircase onboarding (`onboarding.py`, 12-15 Qs across 4 skills, start medium=3) and exact Brier scoring (`scoring.py`).
- Verified via `test_phase2_onboarding.py` (3/3 passed): simulated all-correct -> L4 (Brier 0.01), all-wrong -> L1 (Brier 0.64), random -> L1 (Brier 0.25), overconfident -> capped L1 (Brier 0.4484).
Next: Phase 3 — Levels, tool unlocks, weakest-skill plan, and 12 micro-lessons.
Minor: Tightened Brier calibration floor so blind 50% guessing (Brier >= 0.25) cannot place above L1.
Blockers: none
```

```text
[Divyansh] 45% | Phase 3/6: Levels, Unlocks, Learning Plan & Micro-Lessons
Done:
- Implemented SoT Section 8 cumulative unlocks, `get_user_unlocks()` for Hardhik's `GET /me`, and `ToolLockedError` (HTTP 403 `TOOL_LOCKED`).
- Authored 12 micro-lessons (5-10 min, L1-L3, 3 check questions each) and weakest-skill-first plan generator (`learning.py`).
- Verified via `test_phase3_unlocks_plan_lessons.py` (3/3 passed; 9/9 cumulative).
Next: Phase 4 (Assessments) & Phase 5 (24 curated Indian stock scenarios with price-recomputed outcomes).
Minor: none
Blockers: none
```

```text
[Divyansh] 60% | Phase 4/6: Level-Up Assessments & Tool-Lock Enforcement
Done:
- Implemented `assessments.py` (10 unseen questions + 2 unseen scenarios per level, configurable >=70% & Brier <=0.25 pass criteria, level-up unlocks, fail->plan update).
- Verified via `test_phase4_assessments.py` (3/3 passed — unseen-item filtering, pass/level-up/unlock, fail->plan remediation, configurable Brier gate, duplicate-submission rejection).
Next: Phase 5 — 24 curated 2005+ Indian stock scenarios with live price-data outcome recomputation.
Minor: none
Blockers: none
```

```text
[Divyansh] 80% | Phase 5/6: Curated Historical Indian Stock Scenarios
Done:
- Generated 36 NSE + NIFTY50 historical OHLCV series (`market_prices_seed.json`) and 24 curated 2005+ Indian stock scenarios (`scenarios.yaml`) with zero lookahead and explicit historical disclaimers.
- Verified via `test_phase5_scenarios.py` (2/2 passed; 14/14 cumulative): all 24 scenarios recomputed live from `core.market` with exact match to stored outcomes and NIFTY50 comparison.
Next: Phase 6 — Explain a Stock (30 stocks), Skill Dashboard, Study Mode, 95% CI evidence export, and full FastAPI E2E/security QA.
Minor: Seeded price series tagged `data_origin: synthetic` in offline build; swaps seamlessly to Hardhik's live NSE bhavcopy/yfinance `core.market`.
Blockers: none
```

```text
[Divyansh] 100% | Phase 6/6: Explain a Stock, Dashboard, Study Mode & Evidence Export
Done:
- Precomputed 30 NSE stocks x selected years (`explain_stocks.yaml`) with primary-source citations on every event and guardrailed summaries; implemented `GET /explain` (L2 gated) and `GET /me/dashboard` (L4 gated).
- Implemented Study Mode (`study_pre` / `study_post` with disjoint unseen items) and `export_evidence.py` outputting CSV + JSON with 95% CIs on 40 seeded paired users (Score +32.75% [26.23, 39.27], Brier -0.2721 [-0.3141, -0.2301], Red-flag +45.50% [36.81, 54.19]).
- Full test suite passed: 20/20 (`unittest discover -s services/api/tests/education -v`), including FastAPI HTTP E2E, auth/IDOR/SQLi security checks, and EN+Hinglish guardrail tests.
- Upgraded for live Render + Supabase Postgres deployment: Pydantic v2 `pattern=` validation, dual-mode SQLAlchemy 2 ORM repository, and linear Alembic migration.
Next: Open PR from `feat/education-backend` into `main` excluding dev stubs in `core/` and `main.py`; align with Hardhik on contract extensions in MAJOR update.
Minor: Hardened `GET /explain` symbol parameter with strict allowlist regex after E2E SQLi test caught permissive fuzzy substring matching.
Blockers: none
```

## Ananya

_Web UI (`apps/web`) status as of 2026-11-21._

```text
[Ananya] Web UI | current state
Auth: sign-in and sign-up tabs; sign-out via Neon Auth. The demo workspace has been removed.
Lessons: Looseleaf ChoiceOption radios; lesson checks POST /lessons/{id}/check.
Gating: LockNotice is actionable and gates by level (L1-L4).
Capstone: Nasdaq view (Level 4) on /nasdaq-verifier.
Charts: theme-aware. Dark-theme contrast polished.
Dev fixtures: NEXT_PUBLIC_USE_MOCKS=true (with NEXT_PUBLIC_MOCK_LEVEL) enables fixture mode. It is dev-only and absent from the production bundle.
In progress: mobile navigation.
```

Open items:
- Server-side answer shuffle (Divyansh).
- Top-level `data_origin` missing on some endpoints.
- `/verify` returns 500 without an OpenRouter key.
- Nasdaq challenge store is process-local.
- Live F1 run (Arnav, needs OpenRouter key).
- Real-source seed (Arnav, Option A/B decision from Hardhik).
- CI database name `aacharya_test` (Hardhik).
