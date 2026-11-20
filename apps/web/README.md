# Aacharya web UI

Responsive Next.js UI for the Aacharya learning and source verification flows. It uses the shared API contracts and Neon Auth client from the repository.

## Run locally

```sh
npm install
npm run dev
```

The app opens in mock mode by default. Choose **Explore the demo workspace** to enter with sample data. Mock records carry a **Synthetic data** label.

## API and authentication

Copy the root `.env.example` values into `.env.local` and configure `NEXT_PUBLIC_API_URL`, Neon Auth and database settings as needed. Keep `NEXT_PUBLIC_USE_MOCKS=true` for the demo. Set it to `false` to use the API; the UI sends the Neon Auth JWT as a bearer token.

## Integration notes

The shared API contracts live in `src/lib/contracts.ts`. Several endpoints do not yet include `data_origin`; the client labels fixture data synthetic and requires an explicit origin for live responses. The current PRD is a pending-export placeholder. The dashboard contract contains learning progress series, but no study pre/post export or confidence intervals, so the UI does not present study evidence.
