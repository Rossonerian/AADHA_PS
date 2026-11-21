# Verifier integration

Hardhik's API app owns authentication, sessions, configuration, and the `/api/v1` prefix. Install `requirements.txt` in the platform API environment and bind the actual shared core (no feature-owned clients for LLM, guardrails, or market data):

```python
from app.core import auth, guardrails, llm, market
from app.verifier.jobs import score_open_claims
from app.verifier.ports import VerifierCore
from app.verifier.router import create_router
from app.verifier.service import VerifierService

bindings = VerifierCore(llm.complete, guardrails.check_output, market)
app.include_router(create_router(VerifierService(session_factory, bindings), auth.current_user), prefix="/api/v1")
# Schedule score_open_claims(session_factory, bindings) after each daily market refresh.
```

`session_factory` is a synchronous SQLAlchemy session factory. `current_user` must enforce authentication and return the platform UUID and level. Level 1–2 `/verify` returns `mode="basic"` and null rating facts, label, and score; `/submissions/mine` hides outcomes below Level 3 and source detail requires Level 3. A source score is displayed only after five scored calls. Private submissions are owner-only. Pasted or OCR content and YouTube transcripts can be checked but do not contribute to a public author rating; a transcript does not establish visibility or who made a claim. Edited, forwarded, or otherwise unattributable Telegram captures are not historical rating evidence.

Alembic's current single head, `20261121_merge_verifier_profiles`, joins the independently merged Verifier v2 and profile revisions after `20261121_submission_owner_fk`. The merge adds no schema/data operations. For a complete rollback of both branches, name `20261121_submission_owner_fk` explicitly; relative `-1` is ambiguous at a merge point. Apply only the reviewed migration history before mounting or seeding; never apply production migrations as a local test.

Three evidence bindings are not in SoT §5: `market_cap_bucket(symbol, date)`, `post_deleted(canonical_public_url)`, and `nominal_price_basis(symbol, start, end)`. Supply them only from authoritative observations. Without them, unknown cap and deletion produce no flag, and two-barrier claims stay open rather than comparing nominal prices to potentially incompatible adjusted OHLCV. Linked tips without publication evidence are never scored using the date on which they were found. Price windows use completed NSE sessions after the post; one-session relative claims use that session's open and close. Indistinguishable target/stop order goes to review rather than counting as a win or loss. Confirmed deleted posts stop appearing in shared recent claims but remain in aggregate evidence.

Extraction requires a verbatim source excerpt with independently supported forward direction and explicit entry, target, and stop roles for any quoted levels. If grounding is missing or ambiguous, the claim is marked `needs_review` without the model's disputed fields. Split phone numbers after contact cues are redacted before hashing, storage, and model invocation.

The scoring horizon is checked against the submitted text even when the model omits it from its excerpt. A stated relative duration wins over omission; mismatches, unsupported calendar deadlines, and same-day forecasts are sent to review. The 20-session default is only used when no horizon is detected.

## Reproduce local checks

From `services/api`, with `pytest`, `httpx`, `ruff`, `mypy`, `pandas-stubs`, `types-requests`, and the feature requirements installed:

```sh
python -m pytest -q -s tests/test_verifier_*.py
python -m mypy --explicit-package-bases --ignore-missing-imports app/verifier
ruff check app/verifier tests/test_verifier_*.py ../../db/migrations/versions ../../data/seed/verifier
```

For PostgreSQL migration tests, install `psycopg[binary]` and set `VERIFIER_TEST_DATABASE_URL` to a **disposable** database URL. The test runs the feature revision directly via Alembic Operations; platform revision-chain acceptance is separate.

For the synthetic demo, from the repository root set `PYTHONPATH=services/api` and run `python -m data.seed.verifier.seed --database-url "$DATABASE_URL" --owner "$DEMO_USER_ID"`. The seed user must be a platform user. Paste this exact fixture through `/verify`: `[15/01/2025, 09:15] Demo Forward Desk: XYZDEMO will rise this week. Pakka munafa, last chance!` The API marks the result `synthetic`; its five fictional scored calls are not evidence about any actual source or security. No real source records are shipped without dated, pseudonymised public tips and reproducible market evidence.

After binding the real shared core, run `app.verifier.evaluation.evaluate_file(Path("data/seed/verifier/eval.jsonl"), bindings)` from the repo root. It reports exact structured-match micro F1; wrong structured predictions count as both a false positive and a false negative. Target: ≥0.80. Corpus validation is not a live F1 result. Because earlier development used `eval.jsonl`, its F1 is diagnostic only; formal acceptance needs an independent set.

## Verifier v2

The [approved design](../../../../docs/superpowers/specs/2026-11-21-verifier-v2-design.md)
authorizes timestamped verbatim transcription, pre-publication tip facts, curated
SEBI enforcement and display-only search links. `claim` remains the first claim;
`claims` retains up to five with per-claim facts and evidence offsets. No private
quality score is serialized. Existing eligibility remains conservative, including
YouTube uploader attribution.

Tavily is the sole search adapter: URL/title/content plus optional
`published_date` (ISO or RFC date); unknown publication dates stay null. No query
contains submitted tip text or learner information. Titles are guardrail checked;
search snippets are not presented as verified quotations. Gemini accepts only
canonical public YouTube URLs and transcribes verbatim through `core.transcribe`.
Both providers have typed failures, bounded responses and mocked HTTP tests.

Quality v1 uses three years of strictly earlier sessions, ten-session run-up,
5/60 non-overlapping volume averages, and historical N-session moves. Its fixed
monotone formula is documented in `tip_quality.py`; missing signals stay null.
`TIP_QUALITY_WEIGHT=0` is the deployment default (range 0..10), never auto-written.
`validate_tip_quality.py` is read-only and refuses below 300 real eligible scored
claims across 30 providers. A 70/30 temporal split and within-provider AUC test
must both reach 0.60; no tuning on the late partition.

Quoted-price comparisons require the existing optional `nominal_price_basis`
binding to confirm compatibility for real records. Adjusted closes alone cannot
prove that a historical nominal target shares their basis. Without that evidence,
required-move, target base-rate and stop/reward distances stay null; other
historical facts may remain available. Risk distances are descriptive only and
do not offset a harder target in the private quality formula.

For the complete Verifier, enter `OPENROUTER_API_KEY`, `GEMINI_API_KEY`,
`TAVILY_API_KEY` and `FINNHUB_API_KEY` in the API environment. Tavily uses
`WEB_SEARCH_PROVIDER=tavily`; `WEB_SEARCH_API_KEY` remains an optional legacy
alias if `TAVILY_API_KEY` is unset. `GOOGLE_AI_STUDIO_API_KEY` is likewise an
optional alias for Gemini, not a second required key. Root `.env.example` labels
Neon connection values, generated secrets, and settings that can keep defaults.
General/basic Tavily search requests publication dates, disables generated
answers/raw-page downloads, and retains the 24-hour cache.
