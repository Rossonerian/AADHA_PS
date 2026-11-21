# PaisaProof — 5-Minute Judge Walkthrough Script

> **Total Runtime:** 5:00 (live production: `https://paisaproof.vercel.app`)
> **Core Rule:** Educational investor literacy & deterministic claim verification only — PaisaProof **never** gives buy, sell, or hold advice.

---

## Pre-Demo Prep (2 Minutes Before Pitch)

1. **Wake the Render API** (keep-alive runs every 5 minutes via `.github/workflows/keepalive.yml`, but always verify before going on stage):
   ```bash
   curl -fsS https://aadha-ps.onrender.com/api/v1/health
   ```
   Confirm HTTP `200` with `{"status":"ok","db":"ok",...}`.
2. **Open two browser tabs:**
   - **Tab A (Incognito — Fresh User):** `https://paisaproof.vercel.app` on the clean sign-in screen (use this for Sign-up + Check-in + Level 1 Learning Path + Scenario).
   - **Tab B (Pre-leveled L4 Session or Local Backup):** Either a pre-leveled Level 4 session (so Level 2–4 server-enforced tools — Explain a stock, Source verifier, Progress dashboard, Nasdaq L4 — open immediately without spending 3 minutes taking level-up assessments live) or local dev (`NEXT_PUBLIC_USE_MOCKS=true`, `NEXT_PUBLIC_MOCK_LEVEL=4`).
3. **Copy your Verifier paste snippet** to the clipboard so you never type live:
   ```text
   URGENT! Guaranteed 40% returns in YESBANK by Friday — buy before circuit locks! Telegram @FastAlphaTips
   ```

---

## 5-Minute Live Walkthrough

### 1. Sign-Up / Google OAuth (`0:00 – 0:35`)
- **On screen:** On `https://paisaproof.vercel.app`, click **Sign in with Google** (or switch to **Create account** and submit email + password). Complete the 4-card profile setup (`Continue` through goal, experience, and weekly study time).
- **What to say:**
  > "Retail investors get flooded with screenshots and finfluencer tips every day, yet almost nobody measures whether a tipster actually has a track record — or whether the reader is overconfident. PaisaProof fixes both, without ever giving buy or sell advice. Every account starts real through Neon Auth with an EdDSA JWT — zero hardcoded demo users — and we immediately personalize the learner's study path."

### 2. 6-Question Check-In → Initial Level + Brier Calibration Score (`0:35 – 1:20`)
- **On screen:** Click **Begin check-in**. Answer each prompt and intentionally adjust the **50–100% confidence slider** to match how sure you are. Upon completion, show the placement card: **Level (L1–L4)**, accuracy %, and **Brier score**.
- *(Pacing tip: Pace cleanly through the check-in — ~6 rapid questions shown live on stage, or click briskly through if the live adaptive pool extends up to 12 items — and pause on the final placement summary card.)*
- **What to say:**
  > "Most quizzes only ask if you're right or wrong. PaisaProof asks *how confident* you are on every question and scores you with a Brier calibration score alongside accuracy. If you're confident and wrong, we place your starting level conservatively and build your calibration first."

### 3. Learning Path + Lesson Quick Check (`1:20 – 2:00`)
- **On screen:** Open **Learning path**, click the first unlocked Level 1 lesson card, scan its structured takeaways, and answer the embedded **Quick check** question at the bottom to mark progress.
- **What to say:**
  > "Each learner gets an adaptive Learning path ordered around their weak skills. Lessons take two minutes to read, end with an interactive quick check, and our server enforces progression gates so advanced tools only unlock once you prove calibrated understanding."

### 4. Practice Scenario (`2:00 – 2:40`)
- **On screen:** Click **Practice scenarios** in the left rail. Point out the masked historical NSE price chart and fundamental/news **clues**. Select **Up** or **Down**, check at least one supporting clue, set confidence %, and click **Reveal outcome**. Show actual return vs `NIFTY50` and calibration feedback.
- **What to say:**
  > "Before touching live claims, learners practice on masked historical Indian market setups. You pick a direction, cite the exact financial clues you relied on, rate your confidence, and immediately see the real price move relative to NIFTY50."

### 5. Explain a Stock (`2:40 – 3:20`)
- **On screen:** *(Switch to pre-leveled session if L2+ is locked on the fresh account.)* Open **Explain a stock**, select or enter a seeded NSE case such as `YESBANK` (`2018`), `PAYTM` (`2021`), or `SATYAMCOMP` (`2009`). Highlight the price timeline, major move annotations, `data_origin` badge, and guardrailed summary.
- **What to say:**
  > "At Level 2, investors unlock Explain a stock — an interactive autopsy of famous NSE moves like Yes Bank 2018 or Paytm 2021. Every narrative runs through an English and Hinglish guardrail so it explains *why* prices moved historically with zero buy, sell, or target price language, and every record displays its `data_origin` badge."

### 6. Source Verifier with Deterministic Red Flags (`3:20 – 4:05`)
- **On screen:** Open **Source verifier**, paste the high-pressure sample tip (`"URGENT! Guaranteed 40% returns in YESBANK by Friday — buy before circuit locks! Telegram @FastAlphaTips"`), and submit. Point out:
  - Extracted claim grounded verbatim to the pasted excerpt (symbol, direction, timeframe).
  - Deterministic red-flag chips (`guaranteed_returns`, `urgency`, `not_sebi_registered`).
  - Source profile / historical reliability table and `data_origin` badge.
- **What to say:**
  > "At Level 3, investors unlock the Source verifier. Notice how strict our architecture is: the LLM *only* extracts the structured claim and must ground it to a verbatim quote — it never outputs a verdict or rating. Every red flag — like guaranteed returns, artificial urgency, SEBI surveillance lists, or missing registration — and every source track record is computed deterministically from market and registry data."

### 7. Progress Dashboard (`4:05 – 4:35`)
- **On screen:** Open **My progress**. Briefly highlight skill mastery bars across the four literacy pillars, Brier calibration trend chart, and scenario accuracy breakdown.
- **What to say:**
  > "Over time, My progress tracks skill mastery, scenario accuracy, and Brier calibration in one place — so users can measurably prove their judgment is improving before graduating to Level 4."

### 8. Nasdaq L4 Capstone (`4:35 – 5:00`)
- **On screen:** Open **Nasdaq capstone** (or navigate directly to `/nasdaq-verifier`), select/enter a US ticker (e.g., `AAPL` or `NVDA`), and show factual Finnhub-backed claim grounding and calibration metrics side by side.
- **What to say:**
  > "Finally, Level 4 unlocks our optional Nasdaq capstone — proving the exact same deterministic claim extraction and calibration framework generalizes cleanly beyond NSE and Indian equities to US markets via Finnhub, while staying 100% educational."

---

## Fallback Plan (If Live Data or API Is Slow)

Keep these four fallbacks ready so a slow third-party call never stalls the 5-minute clock:

1. **Render API cold-start or timeout:**
   - Ping `https://aadha-ps.onrender.com/api/v1/health` 2 minutes before presenting to ensure Neon DB + uvicorn are warm alongside `.github/workflows/keepalive.yml`.
2. **Slow or rate-limited LLM extraction in Source Verifier:**
   - The verifier automatically degrades to **`mode: "basic"`**, running deterministic red-flag detection (`guaranteed_returns`, `urgency`, `not_sebi_registered`, surveillance lists) with zero LLM wait. Point this out explicitly as an intentional reliability design.
3. **Google OAuth popup blocked or Neon latency on conference Wi-Fi:**
   - Switch immediately to the inline **Create account / Sign in with email** step on the same auth card — no redirect popup required.
4. **Total venue network / upstream outage (Last Resort):**
   - Switch to **Tab B** running locally with `NEXT_PUBLIC_USE_MOCKS=true` and `NEXT_PUBLIC_MOCK_LEVEL=4`. Tell judges transparently that the backup tab shows deterministic synthetic fixtures (`data_origin: synthetic`) while production runs live on Vercel + Render + Neon.
   - See [`docs/DEMO_BACKUP_CHECKLIST.md`](DEMO_BACKUP_CHECKLIST.md) for full C4 freeze verification and backup recording guidance.
