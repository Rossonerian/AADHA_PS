# Live extraction exact-match F1

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
