# PaisaProof — Team Status

> Updated by everyone in their own section; summarised by **Hardhik** after each checkpoint.
> Progress update format and checkpoint rules: [`docs/SOURCE_OF_TRUTH.md` Section 12](docs/SOURCE_OF_TRUTH.md#12-progress-updates-all-agents).

## Team Summary

| Person | % | Phase | Blockers | Last Update |
|---|---|---|---|---|
| Hardhik | 80% | Phase 6/6 (Integration & Demo — Phases 1–5 complete; C1 live green) | docs/PRD.md export; Divyansh education routes for C2/C3 | 2026-11-21 |
| Arnav | 76.25% | Real seed verified (30×5); Phase 3/6 & 6/6 acceptance open | Hardhik decisions: SoT seed policy, 61 default-horizon quota, OpenRouter quota + held-out set; vetted deletion evidence | 2026-11-21 |
| Divyansh | 100% | Phase 6/6 (Education complete; 20/20 tests pass) | none | 2026-11-20 |
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

```text
[TEAM] C1 | Overall 39%
Arnav 76.25% (Phase 3/6 & 6/6) | Divyansh 0% (Phase 1/6) | Hardhik 80% (Phase 6/6) | Ananya 0% (Phase 1/6; UI PRs #2/#3 merged, % self-update pending)
Behind target: Divyansh (target C1 25%; next target C2 50%) — prioritize P0 onboarding, plan, and lessons before P1/P2 polish
Blockers: docs/PRD.md export pending; Arnav live F1 & real-source Option A/B sign-off; Divyansh education backend routes for C2
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

```text
[Hardhik] 80% | Phase 4/6: CI & deployment (complete -> entering Phase 6/6)
Done: Live C1 verified end-to-end across Vercel (https://aadha-ps.vercel.app), Render API, and Neon (Postgres, Auth, Object Storage, Realtime); CORS preflight 200, /api/neon/health 200 (all 4 services ok), Vercel Auth -> EdDSA JWT -> Render /api/v1/me (401->200), POST /api/v1/verify 200 & GET /api/v1/submissions/mine 200, live daily_job cron logged in job_runs, CI & 286/286 pytest green.
Next: Checkpoint C2/C3 integration with Divyansh education routes & Ananya live UI wiring, update data/DATA_MANIFEST.md, and run full staging smoke test twice before C4.
Minor: Disabled reasoning token overhead for Nemotron models in core.llm so structured outputs do not truncate; guarded /api/neon/verify with 403 in production, hardened CORS/base-URL normalization, and cleaned up README.md and Makefile check commands.
Blockers: docs/PRD.md export; Divyansh education endpoints for full C2/C3 smoke path.
```

## Arnav

_Append updates here._

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
>>>>>>> origin/main
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
