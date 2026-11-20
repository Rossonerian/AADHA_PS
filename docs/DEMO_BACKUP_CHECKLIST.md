# Demo & Backup Checklist (C4 Freeze)

> Gate: **C4 Demo Freeze (Hour 32)** — No new features. Only bug fixes, seed data verification, and backup recording.

## 1. Freeze Rules

- [ ] `main` branch green in GitHub Actions CI (`api` + `web` jobs passing).
- [ ] All PRs merged or closed; no unreviewed feature changes after C4.
- [ ] `docs/SOURCE_OF_TRUTH.md` Rule check verified:
  - No buy/sell/hold advice, price targets, or stock rankings anywhere.
  - All LLM outputs pass `core.guardrails.check_output()`.
  - All demo records display `data_origin` (`real` or `synthetic`) badge in UI.
  - All numbers in UI come from data via templates.

## 2. Double Smoke Test (Staging & Local Backup)

Run the full walkthrough twice end-to-end before demo:

1. **Smoke Test 1 (Production/Staging URL)**
   - [ ] `GET /api/v1/health` returns `200` with `db: ok` and recent `market_data_as_of`.
   - [ ] Onboarding flow (`POST /onboarding/start` -> `POST /onboarding/answer`) completes and assigns level + skills + Brier score.
   - [ ] Learning plan & lesson (`GET /plan`, `GET /lessons/{id}`) load cleanly.
   - [ ] Scenario practice (`GET /scenarios/next`, `POST /scenarios/{id}/answer`) renders chart/context and evaluates answer + clues.
   - [ ] Stock explainer (`GET /explain?symbol=&year=`) renders chart, moves, and guardrailed summary.
   - [ ] Verifier (`POST /verify`, `GET /sources/{id}`, `GET /submissions/mine`) evaluates pasted claim, shows source rating, red flags, and `data_origin` badge.
   - [ ] Dashboard (`GET /me/dashboard`) displays skill progression, Brier score, and scenario accuracy.
2. **Smoke Test 2 (Clean Browser / Fresh User Session)**
   - [ ] Repeat full walkthrough in an incognito browser window using demo credentials.
   - [ ] Confirm zero console errors, zero 500s, and fallback local environment ready if internet drops.

## 3. 3-Minute Backup Demo Recording Script

Record a crisp 1080p MP4 backup video at C4 freeze in case live staging/network fails during pitch:

- **0:00–0:30 — Problem & Promise**: Introduce PaisaProof (investor literacy + source claim verification without ever giving buy/sell advice).
- **0:30–1:15 — Onboarding & Calibration**: Complete onboarding quiz with confidence slider; show level placement, Brier calibration score, and personalized learning plan.
- **1:15–2:00 — Practice & Stock Explainer**: Walk through one historical scenario (clues + market outcome vs NIFTY50) and one `/explain` stock move timeline.
- **2:00–2:45 — Verifier**: Paste a finfluencer claim into `/verify`; highlight source reliability score, SEBI check, red flags (`guaranteed_returns`, `urgency`, etc.), and `data_origin` badge.
- **2:45–3:00 — Guardrails & Dashboard**: Show progress dashboard and note that all outputs are strictly educational and guardrailed.
