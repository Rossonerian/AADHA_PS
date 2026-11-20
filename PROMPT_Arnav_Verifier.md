# Agent prompt — Arnav (Verifier backend & features)

Paste everything inside the code block into your coding agent as its goal, from the repo root.

```text
ROLE: You are the backend engineer for the Verifier module of Aacharya, a hackathon prototype (The Big Hack 2.0, Finance F3). Owner: Arnav.

READ FIRST: docs/PRD.md (Sections 7, 8, 9, 15) and docs/SOURCE_OF_TRUTH.md (SoT). The SoT wins over anything else. Never change a contract in it; if you need a change, stop and send a MAJOR update.

GOAL: Ship the Verifier backend in services/api/app/verifier/: accept a tip (link, pasted text or screenshot), extract the claim, show factual red flags, rate the source (reliable / semi_reliable / not_reliable / not_enough_history), track claims against real prices, and update source ratings over time.

SCOPE: only services/api/app/verifier/, its tests, its Alembic migration files for your tables (coordinate naming with Hardhik), and data/seed/verifier/. Use core.* (SoT Section 5) for auth, LLM, guardrails and market data. No UI, no education code, no infra.

HARD RULES:
- Never output buy/sell/hold advice, targets of our own or stock recommendations. All user-facing text passes core.guardrails.check_output().
- Labels describe sources, never stocks. Every label ships with its facts (calls tracked, correct, deleted, registration).
- Every record has data_origin real|synthetic.
- The LLM only parses and words things; all scoring is deterministic Python with unit tests.
- Never claim a phase done without running its checks and showing the output.
- Git: own branch feat/verifier-*, PRs only, no force-push, never commit secrets.

PLAN (weights add to 100%):
Phase 1 (10%) Models & migration: sources, submissions, claims, source_rating_history per SoT Section 6; Pydantic schemas per SoT Section 7.
  Done when: migration applies on a fresh DB; schema tests pass.
Phase 2 (20%) Ingestion: POST /verify accepts text, image_base64 (OCR; blur/strip phone numbers), public Telegram post URL (t.me/s/...), YouTube URL (transcript). X/Instagram/WhatsApp fall back to text/screenshot with a clear message. Store content_hash + captured_at; dedupe; source identity = platform + handle.
  Done when: one test per input type passes, including a WhatsApp-style paste.
Phase 3 (20%) Claim extraction: core.llm.complete with a JSON schema -> {symbol, direction, entry, target, stop, window, confidence}; core.market.resolve_symbol; Hinglish slang lexicon (tgt, SL, BTST, multibagger, rocket, upper circuit). Vague -> unscorable; low confidence -> needs_review.
  Done when: a labelled eval set of 150 messages (incl. 40 Hinglish) in data/seed/verifier/eval.jsonl gives F1 >= 0.8; report the number.
Phase 4 (15%) Red-flag check (basic mode, available from level 1): codes from SoT Section 8, using core.market (surveillance, volume spike before the post, market-cap bucket) and core.market.sebi_registered.
  Done when: each red-flag code has a passing unit test; /verify returns mode=basic for users below level 3.
Phase 5 (20%) Scoring & ratings: a claim is correct if it beat NIFTY50 in the stated direction over its window (default 20 trading days), or hit target before stop when both exist. Source score = 60% shrunk track record + 25% transparency + 15% red-flag history; labels reliable >= 65, semi_reliable 40-64, not_reliable < 40, not_enough_history if < 5 scored claims. Daily job function score_open_claims() (Hardhik schedules it). Write source_rating_history on every change. Implement GET /sources/{id} and GET /submissions/mine.
  Done when: unit tests cover scoring edge cases (split/bonus, delisted, no target, vague); re-running the job is idempotent.
Phase 6 (15%) Seed & demo data: 30+ sources with >= 5 scored claims each: real public tips (handles pseudonymised, data_origin real) + 6 synthetic personas (accurate, random, pumper, vague, deleter, F&O-heavy). One demo WhatsApp-style tip that lands on a not_reliable source with clear facts. Adversarial test: 100 "should I buy X?"-style inputs return zero directive text.
  Done when: the seed script runs from a clean DB; the demo tip path returns in < 15 s; the adversarial test passes.

PROGRESS % = sum of weights of completed phases + partial credit for the current phase (steps of 25% of that phase).

REGULAR UPDATE (after each phase or every ~2 hours; under 6 lines):
[Arnav] <N>% | Phase <x>/6: <phase name>
Done: <1-3 bullets with evidence: test/command result>
Next: <next step>
Minor: <small issues/decisions or "none">
Blockers: <"none" or what + who is needed>

MAJOR UPDATE (immediately when blocked, when a contract change is needed, when a scope cut is needed, or when a "Done when" check fails and you can't fix it):
[Arnav] MAJOR | <one-line issue>
Impact: <what/who it blocks, deadline risk>
Options: <A / B, with recommendation>
Need from: <person/decision>

Append every update to STATUS.md under "## Arnav" and also print it to me.

START: read the two docs, list any contract gaps you see (as a MAJOR update if they block you), then begin Phase 1.
```
