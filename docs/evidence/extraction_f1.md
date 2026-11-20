# Live extraction exact-match F1

## Re-check attempt: daily quota still exhausted (2026-11-21)

Re-ran `PYTHONPATH=services/api .venv/Scripts/python.exe infra/scripts/evaluate_extraction.py`
on 2026-11-21 (Asia/Calcutta). OpenRouter immediately failed with `ExternalServiceError`
(`total_calls: 0`; daily free-tier quota has not reset). F1 remains **unmeasured (`null`)**.

```json
{
  "corpus": "data/seed/verifier/eval.jsonl",
  "corpus_sha256": "b323a6979c9de91524151c5262b1dc18c0f220edfe4b6b1ffd3e42d1f914c01d",
  "labelled_rows": 150,
  "model": "nvidia/nemotron-3.5-lightning:free",
  "target_f1": 0.8,
  "status": "blocked",
  "reason": "ExternalServiceError",
  "f1": null,
  "usage": {
    "total_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "by_model": {}
  }
}
```

When quota resets (or a paid OpenRouter model is approved), any score on
`data/seed/verifier/eval.jsonl` must be labelled **diagnostic only**, because
earlier grounding work used `eval.jsonl` for recall diagnostics. Proposal: build
an independent held-out acceptance set instead of tuning further on `eval.jsonl`.

## Prior attempt: key loaded, provider quota exhausted

Retried on 2026-11-21 (Asia/Calcutta) after finding the supplied key in
`.env.txt` and copying that file to the ignored `.env` path. The application's
settings now resolve the key and a Postgres URL. Neither file is committed.

OpenRouter returned 41 successful structured responses, then the evaluator
stopped on `ExternalServiceError`. A separate minimal diagnostic request
confirmed **HTTP 429** with a daily-limit message. No alternative model or
provider was selected. F1 remains **unmeasured**, because the 150-row evaluation
did not complete; partial predictions are not a full-corpus score. Failure
classes cannot be inferred from the aggregate usage counters.

Raw evaluator summary (the preceding INFO lines reported per-call token usage):

```json
{
  "corpus": "data/seed/verifier/eval.jsonl",
  "corpus_sha256": "b323a6979c9de91524151c5262b1dc18c0f220edfe4b6b1ffd3e42d1f914c01d",
  "labelled_rows": 150,
  "model": "nvidia/nemotron-3.5-lightning:free",
  "target_f1": 0.8,
  "status": "blocked",
  "reason": "ExternalServiceError",
  "f1": null,
  "usage": {
    "total_calls": 41,
    "prompt_tokens": 12085,
    "completion_tokens": 3661,
    "total_tokens": 15746,
    "total_cost_usd": 0.0,
    "by_model": {
      "nvidia/nemotron-3.5-lightning:free": {
        "calls": 41,
        "prompt_tokens": 12085,
        "completion_tokens": 3661,
        "total_tokens": 15746,
        "cost_usd": 0.0
      }
    }
  }
}
```

The minimal diagnostic returned `ExternalServiceError`, HTTP status `429`,
`daily_limit_mentioned: True`, `rate_limit_mentioned: True`. Provider response
bodies and credentials are omitted. Need sufficient OpenRouter quota for a
complete run; the evaluation-integrity issue below also remains unresolved.
FINNHUB_API_KEY is still absent. Tasks 2–6 remain pending under the stop rule.

## Initial attempt: key not loaded

Attempt date: 2026-11-21 (Asia/Calcutta). Base: `origin/main` at `5f4a89d`.

**BLOCKED. F1 is unmeasured (`null`), not 0.00.** The application's resolved
settings have no `OPENROUTER_API_KEY`. No LLM requests were made and no
predictions or failure classes can be reported. Acceptance target: F1 >= 0.80.
The configured Finnhub key is also absent; the configured database is SQLite.
Tasks 2–6 were not attempted, following the requested stop-on-blocker rule.

## Reproduction

Python 3.11.16, repository root, API development dependencies installed:

```powershell
$env:PYTHONPATH='services/api'
.venv/Scripts/python.exe infra/scripts/evaluate_extraction.py
```

Runner: `infra/scripts/evaluate_extraction.py`. It invokes the existing
`app.verifier.evaluation.evaluate_file()` with `platform_core()` (real
`app.core.llm.complete`, guardrails and market resolver), with no fake client.
Exact matches compare symbol, direction, entry, target, stop and window_days.
Incorrect positive predictions count as FP and FN; missed positives count as FN.
Correct abstentions do not add TP. Corpus and extractor were unchanged.

## Raw command output

```json
{
  "corpus": "data/seed/verifier/eval.jsonl",
  "corpus_sha256": "b323a6979c9de91524151c5262b1dc18c0f220edfe4b6b1ffd3e42d1f914c01d",
  "labelled_rows": 150,
  "model": "nvidia/nemotron-3.5-lightning:free",
  "target_f1": 0.8,
  "status": "blocked",
  "reason": "OPENROUTER_API_KEY is not configured",
  "f1": null,
  "usage": {
    "total_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "by_model": {}
  }
}
```

The runner returns exit code 2 on this configuration blocker.

## Evaluation integrity

Existing Arnav updates in `STATUS.md` explicitly describe earlier grounding
development measured against `eval.jsonl` (30/59 to 59/59 exact-symbol positives
and 1/16 to 14/16 alias positives). Keeping the file unchanged does not preserve
independence after such feedback. A future live result on this corpus should be
labelled a diagnostic; an independent held-out acceptance set or an explicit
decision from Hardhik is needed. No corpus-based tuning was done in this run.
