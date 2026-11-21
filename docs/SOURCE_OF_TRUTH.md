# PaisaProof — Source of Truth

> Repo path: `docs/SOURCE_OF_TRUTH.md`. Owner: **Hardhik**. Others propose changes via a PR titled `contract: ...`; Hardhik approves and updates this file.
> Product spec: `docs/PRD.md` (PaisaProof — Product Requirements Document). If this file and the PRD disagree on a contract, **this file wins**.
> Assumption: "Advisor work" = the **Verifier** (PRD Section 7).

## 1. Work split

| Person | Owns | PRD sections | Code folder | Does NOT touch |
|---|---|---|---|---|
| **Arnav** | Verifier backend & features | 7, 8 (use of filter), 9 (Verifier data), 15 | `services/api/app/verifier/` | UI, education module, infra |
| **Divyansh** | Education backend & features | 6, 9 (education data), 10 | `services/api/app/education/` | UI, verifier module, infra |
| **Hardhik** | Deployment, setup, status, shared core | 8 (filter), 9 (market data), 11, 12, 14, 16 | `services/api/app/core/`, `infra/`, `db/`, CI, `STATUS.md` | Feature logic inside education/verifier |
| **Ananya** | Complete UI | 5, 6–7 (screens), 18 (demo flow) | `apps/web/` | Backend code, DB |

Integration owner: **Hardhik**. Contract owner: **Hardhik**.

## 2. Rules that override everything

1. PaisaProof never tells a user to buy, sell or hold anything, never gives price targets of its own, and never ranks or recommends stocks. Ratings describe **sources**, never stocks.
2. Every LLM output shown to users goes through `core.guardrails.check_output()` before it is returned.
3. Every data record shown in the demo carries `data_origin: "real" | "synthetic"`; the UI shows it as a badge.
4. Numbers in the UI come from our data via templates, never written freely by an LLM.
5. Nobody changes a contract in this file without Hardhik's approval.

## 3. Stack (fixed)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind; charts with Recharts |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic |
| Database & auth | Neon Lakebase Postgres + Neon Auth (Managed Better Auth); Neon Object Storage + Neon Realtime |
| LLM | OpenRouter, called only through `core.llm.complete()` |
| Market data | NSE/BSE bhavcopy or yfinance (`.NS`), loaded by `core.market`; Nasdaq capstone uses Finnhub via `core.finnhub` (env `FINNHUB_API_KEY`, factual endpoints only) |
| Hosting | Web on Vercel; API + cron on Render (or Railway); DB/Auth/Storage/Realtime on Neon |
| CI | GitHub Actions: lint, typecheck, tests on every PR |

## 4. Repo layout

```text
paisaproof/
  apps/web/                     # Ananya
  services/api/app/
    main.py                     # Hardhik
    core/                       # Hardhik: config, db, auth, llm, guardrails, market
    education/                  # Divyansh
    verifier/                   # Arnav
  services/api/tests/
  db/migrations/                # Hardhik (Alembic)
  data/seed/                    # content & seed files (owner per folder)
  infra/                        # Hardhik
  docs/PRD.md
  docs/SOURCE_OF_TRUTH.md
  STATUS.md                     # everyone appends, Hardhik summarises
```

## 5. Shared core interfaces (Hardhik provides; others import)

| Function | Contract |
|---|---|
| `core.auth.current_user()` | FastAPI dependency → `User{id, level}` (verifies Neon Auth EdDSA JWKS or HS256 JWT) |
| `core.llm.complete(prompt, schema=None)` | Returns text or validated JSON; logs cost |
| `core.guardrails.check_output(text)` | Returns `GuardResult{ok, text, reasons}`. Blocks buy/sell/hold, targets, recommendations (English + Hinglish); on fail returns neutral fallback text |
| `core.market.prices(symbol, start, end)` | Adjusted daily OHLCV DataFrame |
| `core.market.index(name, start, end)` | `NIFTY50`, `SENSEX` |
| `core.market.resolve_symbol(text)` | Fuzzy name/alias → NSE symbol or `None` |
| `core.market.surveillance(symbol, date)` | ASM/GSM stage or `None` |
| `core.market.sebi_registered(name_or_reg_no)` | `{found, type, reg_no}` where `type` is `"RA"` or `"IA"` |

### Verifier v2 core additions (approved design, Hardhik reviews implementation)

- `core.transcribe.transcribe(media_url) -> {segments:[{start_s,end_s,text}], language, data_origin}`: verbatim timestamped transcription only, bounded public YouTube input.
- `core.web_search.web_search(query, *, limit) -> [{url,title,published_at|null,snippet,data_origin}]`: one general search adapter, 24-hour query cache; dates remain null when not established as publication dates.

## 6. Database tables

| Table | Owner | Key columns |
|---|---|---|
| users | Hardhik | id, name, current_level (1–4), created_at |
| unlocks | Divyansh | user_id, tool (`scenarios`, `red_flag_check`, `explain_stock`, `verifier`, `dashboard`, `nasdaq_verifier`), unlocked_at |
| skill_scores | Divyansh | user_id, skill_area (`basics`, `reading_stock`, `judging_info`, `risk`), score 0–100, brier, measured_at |
| questions | Divyansh | id, level, skill_area, difficulty 1–5, text, options[], answer, explanation |
| attempts | Divyansh | id, user_id, item_type (`question`, `scenario`, `verifier_guess`), item_id, answer, confidence 50–100, correct, context (`onboarding`, `lesson`, `assessment`, `practice`, `study_pre`, `study_post`), created_at |
| lessons, plans | Divyansh | plan: user_id, lesson_ids[], progress |
| scenarios | Divyansh | id, symbol, as_of_date, window_days, context JSON, outcome JSON, explanation, tags[], difficulty, data_origin |
| sources | Arnav | id, platform, handle, sebi_reg_no, score 0–100, label, scored_claims, data_origin |
| submissions | Arnav | id, user_id, source_id, raw_content, content_hash, captured_at, user_guess, user_confidence |
| claims | Arnav | id, submission_id, symbol, direction (`up`, `down`), entry, target, stop, window_end, scorable, status (`open`, `scored`, `needs_review`, `unscorable`), outcome JSON |
| source_rating_history | Arnav | source_id, score, label, reason, changed_at |

> Platform note (Hardhik): `job_runs` (`id`, `job_name`, `status`, `market_data_as_of`, `details_json`, `ran_at`) is an internal platform table maintained by Hardhik for daily cron observability and `/health`.

> Proposed Verifier hardening (review in this PR): internal `nasdaq_challenges`
> stores `id`, owner `user_id -> users.id`, private template answer strings,
> `expires_at` and `data_origin="real"`. Keys expire after 30 minutes and are
> atomically consumed once by their owner. Expired keys are removed on issuance.
> `submissions.user_id -> users.id` is enforced by a reconciliation revision;
> existing orphaned submissions must be reconciled before deploying it.

Verifier v2 adds nullable `claims.tip_quality` JSON and `tip_quality_version`,
`submissions.transcript_segments` JSON, nullable `sources.enforcement_flag` and
`enforcement_refs` JSON, and `source_rating_history.formula_version`.
`source_mentions` stores id, source_id FK, URL, title, published_at nullable,
platform, fetched_at and data_origin; (source_id, URL) is unique. One submission
may retain up to five grounded claims; remove the previous unique submission FK.

## 7. API contract

All endpoints under `/api/v1`, JSON, auth required except `/health`.

| Endpoint | Owner | Request | Response (key fields) |
|---|---|---|---|
| `GET /health` | Hardhik | – | `{status, version, db, market_data_as_of}` |
| `GET /me` | Hardhik | – | `{id, name, level, unlocks[]}` |
| `POST /onboarding/start` | Divyansh | – | `{session_id, question}` |
| `POST /onboarding/answer` | Divyansh | `{session_id, question_id, answer, confidence}` | `{next_question or null, result?: {level, skills{}, brier}}` |
| `GET /plan` | Divyansh | – | `{level, progress_pct, lessons[{id, title, status, minutes}]}` |
| `GET /lessons/{id}` | Divyansh | – | `{id, title, sections[], check_questions[]}` |
| `GET /scenarios/next?difficulty=` | Divyansh | – | `{id, as_of_date, window_days, context{company, chart[], headlines[], numbers{}}, data_origin}` |
| `POST /scenarios/{id}/answer` | Divyansh | `{direction, confidence, clues[]}` | `{correct, outcome{stock_pct, index_pct}, key_clues[], explanation}` |
| `POST /assessments/{level}/start` | Divyansh | – | `{assessment_id, items[]}` |
| `POST /assessments/{id}/submit` | Divyansh | `{answers[{item_id, answer, confidence}]}` | `{passed, score, brier, new_level?, unlocked[]}` |
| `GET /explain?symbol=&year=` | Divyansh | – | `{chart[], moves[{date, pct, events[{text, source}]}], summary}` |
| `GET /me/dashboard` | Divyansh | – | `{level, skills_over_time[], brier_over_time[], scenario_accuracy[]}` |
| `POST /verify` | Arnav | one of `{url}`, `{text}`, `{image_base64}`; optional `{user_guess, user_confidence}` | `{submission_id, source{id, platform, handle, label, score, facts{}, data_origin}, claim{...}, claims[], tip_facts[{code,text,value,as_of,data_origin}], red_flags[{code, text, evidence{}, data_origin}], mode: "basic" or "full", data_origin}` |
| `GET /sources/{id}` | Arnav | – | `{source, history[], recent_claims[], enforcement{flag,refs[],data_origin}, mentions[], data_origin}` |
| `GET /submissions/mine` | Arnav | – | `{items[{submission_id, claim, status, outcome, data_origin}], data_origin}` |
| `GET /nasdaq-verifier/challenge?symbol=` | Arnav (gate: shared core) | – | `{challenge_id, data_origin: "real", as_of, snapshot{symbol, name, sector, price, day_low, day_high, week52_low, week52_high, market_cap_musd, pe_ttm, chart[], data_origin}, nasdaq_url, disclaimer, questions[{id, text, options[]}]}` |
| `POST /nasdaq-verifier/submit` | Arnav (gate: shared core) | `{challenge_id, answers[{question_id, answer, confidence 50–100}]}` | `{data_origin: "real", passed, score, brier, results[{question_id, correct, correct_answer, explanation}], feedback}` |

Errors: `{error: {code, message}}` with HTTP 4xx/5xx. Locked tool → `403 {error: {code: "TOOL_LOCKED", message, required_level}}`. Missing `OPENROUTER_API_KEY` on `/verify` → `503 {error: {code: "VERIFIER_UNAVAILABLE", message}}`.

**Nasdaq literacy verifier (final capstone, `nasdaq_verifier`).** Not level-granted: unlocked only when `user.level == 4` **and** `plan.progress_pct == 100` **and** calibration `brier <= 0.25`, checked server-side on both endpoints (missing data fails closed). Locked → `403 {error: {code: "TOOL_LOCKED", message, required_level: 4, missing_requirements["level_4"|"plan_progress_100"|"brier_lte_0.25"]}}`. `GET /me` adds `nasdaq_verifier` to `unlocks` only when the gate passes. Data comes from Finnhub (`FINNHUB_API_KEY`), allowlist `/quote`, `/stock/profile2`, `/stock/metric`, `/stock/candle` only; never `/stock/recommendation`, `/stock/price-target` or `/stock/upgrade-downgrade`. Every record is `data_origin: "real"` (REAL badge); questions are template-generated from the numbers; feedback passes `core.guardrails.check_output()`. `nasdaq.com` cannot be iframed, so the UI shows its own snapshot + Recharts chart with an external "Open on Nasdaq.com" link. Extra errors: `FINNHUB_UNAVAILABLE` 503, `NOT_NASDAQ` 422, `INVALID_SYMBOL` 422.

**Verifier v2 rules.** Per-tip output is facts only, never an overall tip score,
label, probability or verdict. `claim` is the first retained claim; additive
`claims` contains up to five, each with `tip_facts` and grounded evidence time
offsets where available. Only strictly pre-publication sessions enter facts.
Registration credit becomes registered with no matched SEBI enforcement order;
match by registration number or exact legal name only. Search mentions are
unverified display links and never enter ratings. Snippets are search excerpts,
not verified page quotations, so the profile displays titles and links only.
`tip_quality_score` stays private with config weight 0 pending independent offline
validation (>=300 eligible scored claims, >=30 providers, temporal test AUC>=0.60
and grouped provider AUC>=0.60). Any manual nonzero weight (max 10) comes from the
15-point red-flag share; the 60-point track record is unchanged. No automatic
activation. Existing public/date/first-sighting eligibility is preserved.

## 8. Shared enums

Proposed hardening details (review in this PR): the capstone gate derives exact
completion from Education's nonempty `plans.lesson_ids` and JSON `progress` map
(every listed lesson must be `completed`), and uses mean Brier across the latest
measurement of each measured skill. Missing, malformed, nonfinite or out-of-range
facts fail closed. Submit requires each issued question exactly once; missing,
duplicate or unknown question IDs return `422 INVALID_ANSWERS` without consuming
the key. Wrong owner, expired, unknown or replayed keys return the same 404.
Verifier validation errors return a neutral message without echoing request data.

Production red-flag evidence is read from deployment-controlled
`data/evidence/verifier/`: AMFI categories require a dated official URL, source
digest and observation/expiry bounds; confirmed deletions require a previous
capture digest, a later timestamp and explicit publisher/platform confirmation
with evidence URL and digest. These files are not populated from user assertions.
Missing evidence remains unknown and produces no finding.

Proposed public-research seed policy (review in this PR): `broker_research`
identifies a corporate publisher, with aliases/renamed brands collapsed. A
dedicated Level-1 import owner owns the public submissions; no demo workspace or
learner history is created. Each claim retains its dated report URL, PDF digest,
page, short field excerpts and adjusted-price/benchmark digests. Date-only
reports use end-of-day Asia/Kolkata for storage, not a claimed publication time.
Scoring uses benchmark sessions strictly after that report date. Source-stated
months map to 20 sessions each and years to 252 (existing extraction convention);
unrepresentable or ranged horizons are excluded. An unstated horizon explicitly
uses the existing 20-session default. Target-only reports use the existing
benchmark-relative policy; their outcomes are not target-hit statistics. Imported
source ratings are limited to this availability-selected historical sample.

- Tip fact codes: `required_move_pct`, `move_base_rate`, `pre_post_run_up_pct`, `pre_post_volume_ratio`, `illiquid_small_cap`, `surveillance_list`, `stop_distance_pct`, `reward_risk`.
- Source labels: `reliable`, `semi_reliable`, `not_reliable`, `not_enough_history`.
- Red-flag codes: `guaranteed_returns`, `urgency`, `illiquid_small_cap`, `surveillance_list`, `pre_post_volume_spike`, `not_sebi_registered`, `vague_claim`, `deleted_post`.
- Levels: 1 Foundations, 2 Reading a stock, 3 Judging information, 4 Risk & discipline.
- Level → unlocks: L1 `scenarios` + `red_flag_check`, L2 `explain_stock`, L3 `verifier`, L4 `dashboard`.
- Capstone unlock (outside the level map): `nasdaq_verifier` — see Section 7 gate rule.

## 9. Integration checkpoints (assumes ~36 h; adjust to the event length)

| Checkpoint | When | What must work |
|---|---|---|
| C0 Contract freeze | Hour 2 | This file merged; Ananya builds on mocks from Section 7 |
| C1 Skeleton live | Hour 8 | Deployed web + API `/health`, auth, DB migrations |
| C2 First vertical slice | Hour 16 | Onboarding end-to-end; `/verify` with pasted text end-to-end |
| C3 Feature complete | Hour 26 | All P0 features live on staging |
| C4 Demo freeze | Hour 32 | No new features; bug fixes, seed data, backup video |

## 10. Dependencies between people

| Needs | From | By |
|---|---|---|
| Repo, docs, contract for mocks | Hardhik | C0 |
| Auth, DB, core.llm, core.guardrails, core.market | Hardhik | C1 (stubs earlier) |
| `/onboarding`, `/plan`, `/lessons` live | Divyansh | C2 |
| `/verify` (text input) live | Arnav | C2 |
| All P0 endpoints live | Arnav, Divyansh | C3 |
| Evidence export for pitch charts | Divyansh | C3 |
| Seeded demo data (sources, scenarios, study) | Arnav, Divyansh | C4 |

## 11. Git rules

- Branch per person: `feat/verifier-*`, `feat/education-*`, `infra/*`, `ui/*`. PR into `main`; CI must pass.
- No force-push, no history rewrite, no deleting others' branches. Never commit `.env` or keys.

## 12. Progress updates (all agents)

**Progress % = sum of the weights of completed phases + partial credit for the current phase** (in steps of 25% of that phase). A phase counts as done only when its "Done when" checks passed.

Regular update (after each phase, or every ~2 hours):

```text
[NAME] 45% | Phase 3/6: <phase name>
Done: <1–3 short bullets, with evidence: test/command result>
Next: <next step>
Minor: <small issues/decisions, or "none">
Blockers: <"none" or what + who is needed>
```

Major update (send immediately):

```text
[NAME] MAJOR | <one-line issue>
Impact: <what/who it blocks, deadline risk>
Options: <A / B, with recommendation>
Need from: <person/decision>
```

Major = blocks another person, needs a contract change, needs a scope cut, fails a "Done when" check you can't fix, or risks a checkpoint.

**Team % = average of the four people's %**, reported by Hardhik after each checkpoint. Anyone below the expected % (C1 25%, C2 50%, C3 85%, C4 100%) is flagged with a proposed scope cut from PRD P1/P2.
