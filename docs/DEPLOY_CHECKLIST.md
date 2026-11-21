# PaisaProof Pre-Test Deployment Checklist

Verify these items across **Render**, **Vercel**, **Neon Auth**, and **Google Cloud** before running an end-to-end test pass on production (`https://paisaproof.vercel.app`).

---

## 1. Render (FastAPI API & Daily Cron)

- **Blueprint Sync:** Sync `infra/render.yaml` in the Render Dashboard so service configuration, health checks (`/api/v1/health`), and cron schedules stay aligned with `main`.
- **Database Migrations (`preDeployCommand`):** `preDeployCommand` (`alembic -c /app/db/alembic.ini upgrade head`) only runs on **Render paid plans (`starter` or above)**. If testing on a free tier, run `alembic -c db/alembic.ini upgrade head` manually against `DATABASE_URL_UNPOOLED` before verifying new endpoints.
- **Required Environment Variables:**
  - `APP_ENV=production`
  - `CORS_ORIGINS=https://paisaproof.vercel.app` *(comma-separated if adding preview/local origins; no trailing slash)*
  - `TRUSTED_PROXY_HOPS=1` *(required behind Render's load balancer so per-IP rate limiting reads the real client IP from `X-Forwarded-For`)*
  - `GEMINI_API_KEY` *(captionless video transcription for Verifier v2)*
  - `TAVILY_API_KEY` *(display-only web search mentions in Verifier v2)*
  - Confirm existing secrets are set: `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `NEON_AUTH_BASE_URL`, `NEON_AUTH_JWKS_URL`, `OPENROUTER_API_KEY`, `FINNHUB_API_KEY`.

---

## 2. Vercel (Next.js Web Frontend)

- **Build-Time Environment Variables:** Set for **Production** (and Preview if testing preview URLs), because Next.js inlines `NEXT_PUBLIC_*` at **build time**:
  - `NEXT_PUBLIC_API_BASE_URL` (and/or `NEXT_PUBLIC_API_URL`) pointing to your Render API base (e.g. `https://<your-render-service>.onrender.com/api/v1`)
  - `NEON_AUTH_BASE_URL` pointing to your Neon Auth instance URL
  - `NEON_AUTH_COOKIE_SECRET` (random >= 32-character secret)
  - `NEXT_PUBLIC_USE_MOCKS=false`
- **Redeploy Cleanly:** After updating any environment variable in Vercel, trigger a fresh deployment **with build cache unchecked** so the client bundle receives updated build-time values.

---

## 3. Neon Auth Console

Open **Neon Console → Project → Auth** and confirm:

- **Trusted Domains / Origins:** Includes `https://paisaproof.vercel.app` (and `http://localhost:3000` for local dev).
- **Google OAuth Provider:** Enabled with your custom **Google Client ID** and **Google Client Secret**.
- **Authorized Redirect URI (Google Cloud → Neon Auth):** Ensure the Google OAuth Web Client authorizes the exact callback URL:
  ```text
  https://ep-misty-paper-azc60pot.neonauth.c-3.ap-southeast-1.aws.neon.tech/neondb/auth/callback/google
  ```
- **Account Linking:** Enable Google/email account linking in Neon Auth settings if available so users with an existing verified email account can also sign in with Google without duplicate-account errors.

---

## 4. Google Cloud OAuth Consent Screen

Open **Google Cloud Console → APIs & Services → OAuth consent screen**:

- **Testing Mode vs Production:** While **Publishing status** is set to **Testing**, add every tester's Gmail address explicitly under **Test users** (or **Publish App** to Production if opening access). Unlisted accounts receive Google `403 access_denied` in Testing mode.
- **Credentials Check:** Confirm your OAuth 2.0 **Web application** client contains both your Google redirect URI above and Authorized JavaScript origin `https://paisaproof.vercel.app`.

---

## 5. 5-Minute End-to-End Smoke Test

Run this quick pass on `https://paisaproof.vercel.app` once all four checklists above are green:

- [ ] **Health Check:** Confirm `GET <API_BASE>/api/v1/health` returns `200` with `"status": "ok"` and `"db": "ok"`.
- [ ] **Email Sign-Up:** Enter a fresh email → confirm inline unknown-user → click **Create account** → verify redirect into Step 1 of profile onboarding.
- [ ] **Onboarding & Reload Resume:** Fill display name (Step 1) → select goal & experience (Step 2) → reload the browser tab on Step 3 and verify it resumes at Step 3 → select weekly pace → click **Find my level** and verify handoff to Question 1 of the placement check.
- [ ] **Google Sign-In:** Sign out (or open an incognito window) → click **Continue with Google** → complete consent → confirm redirect back to `/` with Google name and avatar prefilled in onboarding/topbar.
- [ ] **Lesson Check:** Open Level 1 lesson from Learning Path → submit quick-check answers → confirm score feedback renders and learning path progress updates (`200`).
- [ ] **Verifier Check:** Submit a sample claim/URL (or video tip if Level 3+) → confirm structured claim, red flags, and source summary render cleanly (no 500s).
- [ ] **Sign-Out:** Click **Sign out** → verify session clears and reloading returns to the sign-in screen without cached authenticated data.

## 6. Keep-Alive Ping

- A GitHub Actions workflow (`.github/workflows/keepalive.yml`) requests the Render API health endpoint every 5 minutes to reduce cold starts; the target can be overridden with the `API_HEALTH_URL` repository variable.
- GitHub may delay scheduled runs by several minutes, so the keep-alive is best-effort, not a guarantee.
- For a more reliable backup, add an external pinger such as an UptimeRobot 5-minute HTTP monitor on the same health URL.
