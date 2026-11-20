# Real public-source Verifier seed

Collected on 2026-11-21. Price cutoff: 2026-11-20. This is a real historical
acceptance corpus: **30 corporate publishers, 150 distinct reports/claims, five
scored claims per publisher**, all `data_origin: real`. No demo workspace or
synthetic persona is used by this import.

## Evidence and reproduction

- `data/seed/verifier/real/claims.json`: dated public PDF URL, SHA256, page,
  short numeric-field excerpts, identified security, direction/horizon basis,
  deterministic outcome and price/benchmark digests for each claim.
- `data/seed/verifier/real/prices/`: 112 NSE equity snapshots plus NIFTY50,
  obtained through `core.market` (`yfinance`, adjusted OHLCV). Every bar retains
  provider, as-of date and `data_origin: real`. No model supplies any number.
- `data/seed/verifier/real/nse_symbols.csv`: selected securities from the official
  [NSE equity listing](https://archives.nseindia.com/content/equities/EQUITY_L.csv),
  including ISIN and the observation/source fields. No fuzzy company inference.
- `docs/evidence/real_source_publications.json`: a fresh HTTP 200 and matching
  document hash for **all 150 URLs**, separate from the original downloads.
- Full PDFs, extracted pages and discovery scratch files stay in the ignored
  `data/market_cache/verifier_collection/`; copyrighted report bodies and analyst
  phone/email contact blocks are not copied into the seed or database.

Public research was discovered through the openly listed
[broker report archive](https://storage.googleapis.com/msi-broker-report-archive?prefix=2024&max-keys=1000)
and the publishers' sites, issuer investor-relations archives, and public copies
on Moneycontrol/InvestmentGuruIndia/Business Standard. The author is the research
publisher, not the mirror host. Each final URL identifies the actual PDF whose
bytes were checked; a filename never establishes the report date by itself.

Python 3.11, from the repository root:

```sh
PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py
PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py --check-publications
# Authorized database import; validates the entire bundle before writing:
PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py --load
```

Re-extract the shipped publications into a local review cache, then re-score
through `core.market` (network required):

```sh
python infra/scripts/collect_verifier_sources.py --from-bundle
python infra/scripts/review_verifier_sources.py
PYTHONPATH=services/api python infra/scripts/score_verifier_sources.py
PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py --export
```

Raw discovery mode additionally accepts a local `catalog.json` listing objects
from the public bucket; this scratch catalog is not required to replay the shipped
corpus. Replayed cache selection is limited to that corpus. The broader original
search was availability-selected, not a random sample or an exhaustive publisher
history.

## Selection and scoring limits

Reports span **2023-01-12 through 2025-11-17**. Candidate selection never consults
the eventual return: eligible documents are ordered by report date and document
digest within each publisher, the first ten candidates are checked for market
coverage, and the first five scorable, distinct publisher/security/date claims are
retained. One physical PDF contributes at most one claim. Sector-report copies
indexed under several tickers are collapsed by SHA256.

Axis Direct/Axis Securities, ICICI Direct/ICICI Securities, KRChoksey/Deven Choksey
and Edelweiss/Nuvama are each one publisher, not multiple sources. Report content
must confirm authorship, date, security and a numeric forecast. Scanned text is
subject to the same checks; the retained SBI reports have readable text fields.
Printed report dates take precedence over discovery filenames, price-reference
dates and dates mentioned in the business discussion.

**89 claims have a stated horizon; 61 explicitly use the existing 20-session
Verifier default because no supported source horizon was established.** Stated
months map to 20 trading sessions per month; a stated year maps to 252, matching
the existing extraction convention. This is an approximation, not calendar-month
or anniversary scoring. Ranged/overlong horizons (for example 6–9, 12–18 or 18–24
months), missing price endpoints, ambiguous securities, and target/stop calls
without a demonstrated shared nominal/adjusted basis are excluded. A source's
unsupported horizon is never silently replaced by the default. Numeric price
ranges are retained as ranges; their midpoint is not invented as an entry.

These are **benchmark-relative directional outcomes**, not target-hit rates.
The existing `evaluate_claim()` uses first-to-last adjusted closes over benchmark
sessions strictly after the report date when both target and stop are not present.
Targets here are historical source quotations, not PaisaProof targets, executable
entries or model-generated advice. Date-only timestamps are stored at the end of
the Asia/Kolkata day; no exact release time is asserted. The frozen outcomes are
80 positive signed-excess outcomes and 70 negative ones; they are not a population
accuracy estimate or a stock/publisher recommendation.

Five claims are the requested minimum, not enough to establish broad reliability.
The set favors accessible, parseable reports and surviving listed securities.
Unknown registration stays unknown. No deleted-post evidence or findings are
invented. Source ratings follow the existing formula over these observations and
must be interpreted with this sample limitation.

## Publishers

| Corporate research publisher | Scored claims |
|---|---:|
| Anand Rathi Securities | 5 |
| Asit C. Mehta | 5 |
| Axis Securities | 5 |
| BOB Capital Markets | 5 |
| BP Wealth | 5 |
| Centrum Broking | 5 |
| Choice Broking | 5 |
| Deven Choksey / KRChoksey | 5 |
| Dolat Capital | 5 |
| East India Securities | 5 |
| Elara Securities | 5 |
| Emkay | 5 |
| Geojit | 5 |
| HDFC Securities | 5 |
| Hem Securities | 5 |
| ICICI Securities / ICICI Direct | 5 |
| IDBI Capital | 5 |
| IIFL | 5 |
| JM Financial | 5 |
| Keynote Capitals | 5 |
| Kotak Securities | 5 |
| LKP Securities | 5 |
| Motilal Oswal | 5 |
| Nirmal Bang Institutional Equities | 5 |
| Nuvama / Edelweiss | 5 |
| Prabhudas Lilladher | 5 |
| Religare | 5 |
| SBI Securities | 5 |
| Sharekhan | 5 |
| Systematix Shares & Stocks | 5 |

## Validation output

```text
$ PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py
{"status": "validated", "claims": 150}
$ PYTHONPATH=services/api python infra/scripts/load_real_verifier_seed.py --check-publications
{"public_pdfs_verified": 150, "digest_matches": 150}
```

Disposable Postgres verification (isolated schema at Alembic head
`20261121_submission_owner_fk`, dropped after check; production migrations not
applied):

- `load_real_verifier_seed.py --load` ran twice (idempotent):
  `{"status": "loaded", "data_origin": "real", "sources": 30, "claims": 150, "min_scored_claims": 5}`.
- Verified 30 sources, 150 submissions, 150 claims, `data_origin={"real"}`,
  `min_scored_claims=5`.
- Spot-checked 10 random claims across 10 distinct publishers (`idbi_capital`/TCS,
  `centrum_broking`/BALRAMCHIN, `dolat_capital_market`/CIPLA, `emkay`/DABUR,
  `prabhudas_lilladher`/HINDPETRO, `keynote_capitals`/IGPL, `axis_securities`/CYIENT,
  `elara_securities`/CMSINFO, `nirmal_bang_institutional_equities`/INDUSINDBK,
  `anand_rathi_securities`/PRICOLLTD) directly against the fetched PDF bytes:
  10/10 matched publisher, report date, security, direction, and price levels.
- Privacy & copyright scan: 0 analyst emails, 0 phone numbers, max excerpt
  length 42 chars; no report bodies stored. `data/market_cache/` is gitignored.

The loader uses one transaction and a dedicated Level-1 public-import owner.
It verifies the quota, source/price origins, unique reports and logical claims,
snapshot hashes, and deterministic outcomes before beginning the transaction.
Phone redaction precedes content hashing. Replaying the same bundle preserves
submission IDs and source claim counts. Tests also reject mixed synthetic claims,
synthetic price rows even with recomputed hashes, incomplete price windows,
duplicate PDFs, altered hashes and a source below its five-claim quota.

This seed does not resolve the separate OpenRouter F1/held-out integrity,
Hardhik's decision on the 61 default-horizon claims, or reviewed-deletion
evidence gates.
