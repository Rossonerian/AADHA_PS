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

Alembic revision `20261120_verifier` owns only the four Verifier tables. Coordinate its independent head with the platform history and add the `submissions.user_id` → `users.id` FK after confirming the platform identity type. Apply the platform migration chain before mounting or seeding.

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

After binding the real shared core, run `app.verifier.evaluation.evaluate_file(Path("data/seed/verifier/eval.jsonl"), bindings)` from the repo root. It reports exact structured-match micro F1; wrong structured predictions count as both a false positive and a false negative. Target: ≥0.80. Corpus validation is not a live F1 result.
