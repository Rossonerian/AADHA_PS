## Arnav

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
