# PaisaProof — Product Requirements Document (PRD)

> `[PENDING EXPORT: Drop exported PRD.md here before C0 freeze]`

- Contract precedence: If `docs/PRD.md` and `docs/SOURCE_OF_TRUTH.md` disagree on any contract, `docs/SOURCE_OF_TRUTH.md` wins.
- Platform & Shared Core scope (Hardhik): Sections 8, 9, 11, 12, 14, 16.

## Final-Level Nasdaq Literacy Verifier (capstone)

> Proposed addition (contract change pending Hardhik approval). `docs/SOURCE_OF_TRUTH.md` wins on any contract conflict.

After a learner finishes Level 4, the full learning plan, and shows calibration (Brier <= 0.25), the `nasdaq_verifier` tool unlocks. It proves the learner can read real market data: a neutral Nasdaq snapshot (price, day and 52-week range, market cap, P/E TTM, sector) plus a price chart, followed by 3-4 objective data-reading questions with a 50-100% confidence slider, scored by accuracy and Brier.

No-recommendation compliance:
- Never gives buy, sell or hold guidance, price targets, analyst consensus, ratings gauges or stock rankings; the ticker selector is user search or the neutral NDX benchmark, never "top picks".
- Finnhub endpoint allowlist: `/quote`, `/stock/profile2`, `/stock/metric`, `/stock/candle`. Recommendation, price-target and upgrade/downgrade endpoints are never called.
- All records carry `data_origin: "real"` and show a REAL badge; numbers come from templates, not an LLM; any worded feedback passes `core.guardrails.check_output()`.
- The unlock is enforced server-side (`403 TOOL_LOCKED`); the UI is never the gate.
- `nasdaq.com` blocks iframes, so the app renders its own data and links out to `https://www.nasdaq.com/market-activity/stocks/<symbol>` for cross-checking.
