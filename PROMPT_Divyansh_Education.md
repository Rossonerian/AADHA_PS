# Agent prompt — Divyansh (Education backend & features)

Paste everything inside the code block into your coding agent as its goal, from the repo root.

```text
ROLE: You are the backend engineer for the Education module of PaisaProof, a hackathon prototype (The Big Hack 2.0, Finance F3). Owner: Divyansh.

READ FIRST: docs/PRD.md (Sections 6, 9, 10) and docs/SOURCE_OF_TRUTH.md (SoT). The SoT wins over anything else. Never change a contract in it; if you need a change, stop and send a MAJOR update.

GOAL: Ship the Education backend in services/api/app/education/: adaptive onboarding quiz with confidence, levels and tool unlocks, personal learning plan with lessons, level-up assessments, historical scenarios with reveal, Explain a Stock, and the skill dashboard + evidence-study data that proves users improve.

SCOPE: only services/api/app/education/, its tests, its migration files (coordinate naming with Hardhik), and data/seed/education/. Use core.* (SoT Section 5) for auth, LLM, guardrails and market data. No UI, no verifier code, no infra.

HARD RULES:
- Never tell users to buy/sell/hold or predict future prices. Scenarios are historical learning exercises and say so. All LLM text passes core.guardrails.check_output().
- Lesson facts are written by us; the LLM may only personalise order/examples or word grounded explanations from stored data, citing a source for every event.
- Every scenario and seed record has data_origin real|synthetic.
- Never claim a phase done without running its checks and showing the output.
- Git: own branch feat/education-*, PRs only, no force-push, never commit secrets.

PLAN (weights add to 100%):
Phase 1 (10%) Models & migration: unlocks, skill_scores, questions, attempts, lessons, plans, scenarios per SoT Section 6; content loader for data/seed/education/*.yaml.
  Done when: migration applies on a fresh DB; the loader imports a sample file; tests pass.
Phase 2 (20%) Onboarding: adaptive 12-15 questions across 4 skill areas, each with confidence 50-100; start medium, harder after correct, easier after wrong. Output level 1-4, per-skill scores and Brier score. Endpoints per SoT Section 7. Question bank: >= 80 questions across levels 1-3 (>= 10 per skill area per level).
  Done when: simulated users (all-correct, all-wrong, random, overconfident) land at sensible levels; Brier is computed correctly in tests.
Phase 3 (15%) Levels, unlocks, plan & lessons: level -> tool unlocks per SoT Section 8; plan built from the weakest skills; >= 8 micro-lessons (5-10 min) for L1-L3, each with 3 check questions; GET /plan, GET /lessons/{id}; expose unlocks for Hardhik's GET /me.
  Done when: a new user gets a plan targeting their weakest skill; unlock rules are tested.
Phase 4 (15%) Assessments: 10 questions + 2 scenarios per level from unseen items; pass = >= 70% correct AND Brier within threshold (configurable, default <= 0.25); a fail updates the plan; 403 TOOL_LOCKED handled consistently.
  Done when: pass / fail / level-up / unlock flows are covered by tests.
Phase 5 (20%) Scenarios: >= 20 curated scenarios from 2005+ Indian stocks with real prices (core.market): context (company, chart up to as_of_date, 2-4 headlines, key numbers), window_days, tags (pump_and_dump, earnings_surprise, hype_no_fundamentals, ...), difficulty. The answer endpoint scores direction vs the actual move and vs NIFTY50, and returns key clues and an explanation.
  Done when: every scenario's outcome is recomputed from price data in a test (no hand-typed outcomes).
Phase 6 (20%) Explain a Stock + dashboard + evidence: precompute GET /explain for ~30 stocks x selected years (biggest moves, events with sources, grounded summary); GET /me/dashboard; study mode (context study_pre / study_post with unseen items) and an export script that outputs pre/post score, Brier change and red-flag detection change with 95% CIs as CSV + JSON for the pitch chart.
  Done when: every event line in explain responses has a source; the export runs on seeded study data.

PROGRESS % = sum of weights of completed phases + partial credit for the current phase (steps of 25% of that phase).

REGULAR UPDATE (after each phase or every ~2 hours; under 6 lines):
[Divyansh] <N>% | Phase <x>/6: <phase name>
Done: <1-3 bullets with evidence: test/command result>
Next: <next step>
Minor: <small issues/decisions or "none">
Blockers: <"none" or what + who is needed>

MAJOR UPDATE (immediately when blocked, when a contract change is needed, when a scope cut is needed, or when a "Done when" check fails and you can't fix it):
[Divyansh] MAJOR | <one-line issue>
Impact: <what/who it blocks, deadline risk>
Options: <A / B, with recommendation>
Need from: <person/decision>

Append every update to STATUS.md under "## Divyansh" and also print it to me.

START: read the two docs, list any contract gaps you see (as a MAJOR update if they block you), then begin Phase 1.
```
