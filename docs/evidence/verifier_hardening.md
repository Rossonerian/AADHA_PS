# Verifier hardening: 2026-11-21

Branch: `feat/verifier-real-acceptance`, PR #9. API/backend only; no web changes.

## Real-data gates

The user explicitly chose **keep the real-data gate open**, not Option B.
No synthetic sources or prices were loaded or relabelled. Read-only aggregate
checks of configured Postgres returned:

```json
{"backend": "postgresql", "deployed_revision": "20261120_01_edu", "qualifying_real_public_sources": 0}
```

A qualifying source here has real source/submission/claim origin, a dated public
post URL, at least five scored rating-eligible claims, and a non-private handle.
The required 30 sources remain missing. Public brokerage-report archives were
located, including [Sharekhan's February 2025 guide](https://www.sharekhan.com/MediaGalary/Equity/ValueGuide_Feb2025.pdf),
but locating reports is not proof of 150 vetted, price-grounded claims. No source
counts or scored outcomes were inferred from search snippets.

Live extraction F1 remains blocked by OpenRouter quota; see
[the separate extraction evidence](extraction_f1.md). Earlier corpus-feedback
development also compromises its held-out status.

## Nasdaq persistence and owner reconciliation

`20261121_nasdaq_challenges` adds private Postgres-backed answer keys with an
owner FK and 30-minute TTL. `DELETE ... RETURNING` checks key, owner and expiry
in one atomic operation. Keys survive a fresh Python process; concurrent submits
have one winner; a wrong owner cannot consume a key. Incomplete, duplicate or
unknown question IDs roll back consumption. Submitted answer text is neither
stored nor echoed. Expired keys are cleaned on subsequent issuance.

`20261121_submission_owner_fk` adds `submissions.user_id -> users.id` without
inventing users or deleting orphaned records. The migration deliberately fails
if deployed records have unmatched owners. Up/down/re-up and an invalid-owner
write are tested with a pre-existing submission retained. Postgres tests create
and remove fresh `verifier_acceptance_<random>` schemas, never migrate the
application schema. Production migrations have not been applied by this PR.

The gate now reads Education's actual JSON lesson-status map and latest Brier
per measured skill instead of coercing a JSON object to a float. Exact 100%
completion and finite Brier in [0, 0.25] are required with Level 4. Missing and
invalid facts fail closed. Both routes retain the server-side gate.

## Live Finnhub observation

Run with `PYTHONPATH=services/api` and Python 3.11:
`python infra/scripts/check_finnhub_live.py`. It prints no credentials or
recommendation endpoints. Raw result:

```json
{
  "checked_at": "2026-11-20T21:51:56.685734+00:00",
  "status": "ok",
  "snapshot": {
    "symbol": "AAPL",
    "price": 342.56,
    "day_low": 340.56,
    "day_high": 354.34,
    "week52_low": 243.42,
    "week52_high": 360.83,
    "market_cap_musd": 5074783.326486622,
    "pe_ttm": 38.4604,
    "data_origin": "real"
  },
  "chart_points": 0,
  "question_count": 4,
  "endpoints": {
    "/quote": 200,
    "/stock/profile2": 200,
    "/stock/metric": 200,
    "/stock/candle": 403
  }
}
```

This is 2026-11-21 in Asia/Calcutta. Candles were plan-restricted: the API retains
the real snapshot and factual questions but returns an empty chart. No chart is
fabricated and no secondary provider is substituted. Missing required snapshot
data still prevents challenge issuance. This probes live provider data; endpoint
abuse tests below use controlled snapshots rather than claim live API traffic.

## Evidence and privacy

Market-cap evidence now binds to 2,245 dated, hash-identified AMFI NSE records;
see [provider provenance and review rules](../../data/evidence/verifier/README.md).
Deletion provider binding requires a reviewed previous capture plus explicit
publisher/platform confirmation. Its production registry is empty, so no real
deletion finding is asserted. Missing evidence continues to mean no finding.

Endpoint tests exercise the existing 100 adversarial requests and 300 EN /
Hinglish / obfuscated guardrail cases against both `/verify` and
`/nasdaq-verifier/submit`. Test extraction and Finnhub inputs are controlled;
the production output guardrail runs. Rendered response prose is checked rather
than JSON field names such as a quoted claim's `target`. Phone numbers are
redacted before content hashing, storage and model prompts; submitted Nasdaq
answer text is never persisted. Oversized and extra-field payloads receive
neutral validation errors without reflecting instructions or PII.

## Validation

Python 3.11.16, complete API suite with isolated Postgres persistence cases
enabled (no skips):

```text
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

The warning is Starlette's TestClient `httpx` deprecation. The test process loaded
`VERIFIER_POSTGRES_TEST_URL` from local settings without printing it, then set
application `DATABASE_URL=sqlite://`, `DATABASE_URL_UNPOOLED=""`, `APP_ENV=test`.
The Postgres fixture used six fresh schemas and removed each after its test.
No production migrations or seed writes were performed.
