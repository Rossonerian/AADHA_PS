# Verifier evidence

These files are deployment-controlled provenance, not user assertions. Every
entry must be reviewed before commit. They are separate from source-call seed
data and do not satisfy the 30-source / five-scored-claims quota.

`market_cap.json` contains 2,245 unambiguous NSE rows extracted from AMFI's
[official January–June 2026 classification](https://portal.amfiindia.com/spages/AverageMarketCapitalization30Jun2026.pdf).
Each entry includes the PDF digest, page, average market cap in INR crore,
period end, observation date and expiry. The importer refuses a changed source
digest, duplicate NSE symbols or an unexpectedly small import. Wrapped or
ambiguous PDF rows are omitted. The file is sorted by symbol; it is not a
recommendation or performance ranking.

Reproduce from the repository root with Python 3.11 and API dev dependencies:

```powershell
$env:PYTHONPATH='services/api'
.venv/Scripts/python.exe infra/scripts/import_amfi_evidence.py
```

Observation began on 2026-11-21. These categories cannot support findings for
earlier submissions. Expiry is conservatively limited to 2026-12-31, the end of
the next reporting period; a new snapshot requires review. Classification alone
does not trigger illiquidity: the existing volume threshold must also pass.

`confirmed_deletions.json` is intentionally empty: no real post deletion has been
independently confirmed for this run. Do not populate it from 404s, login walls,
timeouts, absence from search or unverified user reports. A reviewed record must
include an exact post URL, earlier capture timestamp and SHA256 of the **phone-
redacted** capture, a later timezone-aware confirmation timestamp, explicit
publisher confirmation or platform deletion notice, and a public evidence URL
with the notice's SHA256. Keep only provenance and digests, never personal
contact details. Future or invalid confirmations remain unknown. This registry
is not a live deletion crawler; a reviewer must verify the linked notice and
digests before deployment.

`platform_core()` binds both providers. Missing, stale, malformed, conflicting or
synthetic evidence yields no finding. Any evidence hash or public URL in a
response is factual metadata, not LLM-generated text.
