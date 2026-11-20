# Aacharya web UI

Responsive Next.js UI prototype for the Aacharya learning and source-verification flows. It stays inside the `apps/web/` ownership boundary.

## Run locally

```sh
npm install
npm run dev
```

The app opens in mock mode by default. Choose **Explore the demo workspace** to enter with sample data. The sample records are labeled **Synthetic data** in the UI.

## Connect the API and Supabase

Copy `.env.example` to `.env.local`, then set the API base URL and Supabase public URL/key. Set `NEXT_PUBLIC_USE_MOCKS=false` to use the API. The UI sends the Supabase access token as a bearer token to the API.

## Contract items to confirm before live integration

- `docs/PRD.md` is referenced by the UI brief but is not present on the checked out `origin/main`.
- The source contract does not include `data_origin` on every response whose data is shown, including plan, lesson, assessment, and onboarding results.
- Several response field shapes need detail: onboarding question/result fields, lesson section and check-question shapes, assessment item shapes, verifier claim/outcome details, and source `facts`.
- The contract returns verifier `mode: basic | full`, but does not define which levels receive each mode.
- The dashboard contract has progress series but no study pre/post export or confidence intervals. The UI labels its current chart fixtures synthetic and does not fabricate study evidence.

Until those items are resolved, the UI uses conservative local fixtures and does not claim that mock results are live market data.
