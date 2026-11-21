# Verifier v2 — Design

Date: 2026-11-21 · Status: approved 2026-11-21 · Owner: Verifier (Arnav), reviewed by Hardhik for core changes

## 1. Intent

A user submits one stock tip (a link or a message). The Verifier judges the
**tip provider**, using evidence from that tip, the provider's history and
checkable facts about them, and shows the user plain facts about the **tip**.
Over time, each provider's reliability is updated from the real outcomes of
their tips.

The app never says whether a stock will rise or fall, never says "act" or
"don't act", and never puts a reliability percentage on an individual tip
(SoT rule 1: "Ratings describe sources, never stocks").

## 2. Goals, non-goals, anti-goals

**Goals**
- Accept Telegram, YouTube, Instagram, X and plain-text tips.
- For every tip, show factual red flags and plausibility facts about the tip.
- For every provider, keep a 0–100 reliability score grounded in real outcomes.
- Record a tip-quality score for every tip, so we can later test whether it
  predicts outcomes.

**Non-goals (this version)**
- Forecasting a stock's direction, by a model or by rules.
- Automated reading of Instagram or X posts. Their official APIs don't allow
  it, and scraping breaks their terms. These links stay paste or screenshot only.
- Social-media sentiment counting toward the score.

**Anti-goals (failure even if it "works")**
- Any per-tip number or wording a user could read as "the chance this works".
- A provider's score moving because of a model's view of the stock.
- A named person's score lowered by rumours, or by a tip that can't be traced
  to a public post they made.
- An LLM paraphrase being scored as if the provider said it.

## 3. Constraints (from the repo and SoT)

- Every user-facing string passes `core.guardrails.check_output`. Numbers in
  the UI come from our data via templates, never written freely by an LLM.
- LLM calls go only through `core` (`core.llm.complete` for OpenRouter text;
  new `core.transcribe` for audio/video). Features never call a provider directly.
- Extraction keeps today's grounding rule: a verbatim excerpt from the source
  text must support the stock, the direction and every price level. If not,
  the claim goes to `needs_review`.
- Rating eligibility keeps today's rules (`Claim.rating_eligible`): the tip
  is traceable to a public post with a trustworthy publication date, is the
  first sighting of that post, and isn't pasted, OCR'd or a forwarded
  capture. A source score is shown only after 5 scored calls.
- Scoring windows start at the post's publication date, never the date it
  was submitted.

## 4. Approaches considered

| Approach | Trade-off | Decision |
|---|---|---|
| A. Model forecasts the stock's direction; tipster credited before the outcome | A disguised stock call that leaks through the rating; mostly noise over 5–20 sessions; the real outcome arrives anyway | Rejected |
| B. Tip-quality signals (how plausible and how pump-like the call is) feed the rating immediately | Unproven signal moves real people's scores | Rejected |
| C. Tip-quality signals are recorded silently, tested against real outcomes, then added at a small weight only if they predict outcomes | Slower; needs enough scored claims before it can help | **Chosen** |

## 5. Pipeline

```
submit → 1 ingest → 2 extract claim → 3 tip facts (stored + shown)
                                    → 4 provider profile (shown)
       → daily job: 5 score outcome → 6 update provider reliability
       offline: 7 validate tip-quality score
```

### 5.1 Ingest (`verifier/ingestion.py`)

| Input | Method | Rating-eligible? |
|---|---|---|
| Telegram public post link | Existing fetch | Yes (existing rules) |
| YouTube link | Existing caption transcript; **new:** if there are no captions, transcribe the audio with timestamps | Yes if the channel and publish date resolve (existing rule) |
| Instagram / X link | Stays paste-only (existing `_PASTE_ONLY_HOSTS`): ask for a screenshot or pasted text | No |
| Screenshot | Existing local OCR (rapidocr) | No |
| Pasted text | Existing | No |

- **Transcript, never summary.** Videos are transcribed, not summarised, so
  extraction can still quote the provider's exact words. A summary may be
  generated for **display only** and is never fed to extraction or scoring.
- Store the transcript segment timestamps. The claim's evidence excerpt keeps
  its time offset, so a reviewer can jump to the moment it was said.

### 5.2 Extract the claim (`verifier/extraction.py`)

Unchanged: an LLM call through OpenRouter with a fixed JSON schema, then
deterministic grounding checks. For long transcripts, run extraction per
transcript chunk and keep every grounded claim (cap: 5 per submission; the
`claims` table already allows several claims per submission).

### 5.3 Tip facts (new module `verifier/tip_quality.py`)

Each fact is computed only from data available **at the post's publication
date**, so a tip is never judged with information from after it was posted.

| Signal | Definition |
|---|---|
| `required_move_pct` | Move needed to reach the target from the last close before the post. With no target: null |
| `move_base_rate` | Share of this stock's past N-session windows (last 3 years) where the tip would have counted as correct, where N is the tip's window. With a target: a move at least `required_move_pct` in the tip's direction. With no target: positive return relative to NIFTY in the tip's direction, the same test `evaluate_claim` uses |
| `pre_post_run_up_pct` | Stock return over the 10 sessions before the post |
| `pre_post_volume_ratio` | Average volume over the 5 sessions before the post ÷ average volume over the previous 60 sessions (maps to the existing `pre_post_volume_spike` red flag) |
| `illiquid_small_cap` | Existing red flag, when its data is available |
| `surveillance_list` | Existing red flag |
| `stop_distance_pct` / `reward_risk` | Only when both target and stop are stated |

- **Shown to the user** as templated facts, for example: "This needs a +18% move in 5
  sessions. This stock moved that much in 3% of past 5-session windows." Plus
  the red flags. No overall per-tip score, label or percentage is ever shown.
- **Stored:** every signal, plus `tip_quality_score` (0–1, from a fixed
  formula, version-tagged), in a new `claims.tip_quality` JSON column. Its
  weight in the rating starts at 0.

### 5.4 Provider profile

- **Counts toward the score (checkable facts only):** SEBI registration (existing
  `core.market.sebi_registered`), plus, **new**, any SEBI enforcement orders
  naming the provider, matched by registration number or exact legal name.
  Source: a curated seed file `data/seed/market/sebi_orders.csv` (columns
  `reg_no, name, order_date, order_url, summary, as_of_date, data_origin`),
  maintained like the existing `sebi_ra_ia.csv`. SEBI publishes orders as
  PDFs with no API, so no live scraping.
- **Shown, not scored:** a "What people are saying" panel listing links found by
  search, with titles and dates. Search goes through a general web search
  API (decided by the owner) behind a new `core.web_search(query, *, limit)`
  that returns `[{url, title, published_at | None, snippet}]`. One provider
  adapter, configured by `WEB_SEARCH_PROVIDER` / `WEB_SEARCH_API_KEY`.
  Results are cached for 24 h per query. Queries use the handle and platform
  only; no user data goes into a query. No LLM verdict or sentiment score. Any
  LLM-written snippet must quote the linked post and pass the guardrails.
- **Identity:** a provider is one `(platform, handle)` pair. Cross-platform
  links are made only from the provider's own profile (for example, the YouTube
  channel's "About" links), never from a name match.

### 5.5 Score the outcome (existing daily job)

Unchanged `evaluate_claim`, run after the market refresh: the stock against
NIFTY over the sessions after the post, or whichever of target and stop is
hit first.

### 5.6 Provider reliability (`verifier/scoring.py::rate_source`)

Today: `60 × track record + 12.5 × (posts kept + registration) + 15 × clean
of red flags`. Changes:
- The registration term becomes "registered and no enforcement order".
  Enforcement found → 0.
- A `tip_quality` term is added at **weight 0** until §5.7 passes. If it
  passes, it may take up to 10 points, taken from the red-flag share. The
  track record stays at 60 points.
- Each recomputation writes a `source_rating_history` row (existing), now
  including the formula version.

### 5.7 Validate the tip-quality score (offline script)

- **When it runs:** only once there are ≥ 300 rating-eligible scored claims from ≥ 30
  providers (not enough data otherwise).
- **Test:** split claims by when they were posted (train on earlier tips,
  test on later ones). Compare how often low- and high-quality tips turned out
  correct, using area under the ROC curve (AUC) and calibration buckets.
  Report both.
- **Pass:** AUC ≥ 0.60 on the later tips, and the gap holds when results are
  grouped by provider. Passing means a person sets the weight by editing
  config. It is never switched on automatically.

## 6. Data changes

- `claims.tip_quality` (JSON, nullable) and `claims.tip_quality_version`
  (string).
- `submissions.transcript_segments` (JSON, nullable).
- `sources.enforcement_flag` (bool, nullable) and `sources.enforcement_refs`
  (JSON).
- New table `source_mentions` (id, source_id, url, title, published_at,
  platform, fetched_at). Display only.
- Alembic revision chained after the current head.

## 7. What's left to the builder

- Exact sizes of the windows in §5.3 (3 years / 10 / 5 / 60 sessions are
  starting points).
- The tip-quality formula. Keep it monotone and documented, and version it.
- Chunk size for long transcripts.
- UI layout of the tip-facts card and the "What people are saying" panel.

## 8. Calls made without the owner

- **Transcription:** Gemini through Google AI Studio for videos without
  captions, because most OpenRouter models can't take audio or video. This
  adds a second provider beside OpenRouter, behind a new `core` function
  (`core.transcribe`, owned by Hardhik), so features still don't call
  providers directly.
- SEBI enforcement orders come from a curated seed CSV, not live scraping.
- `core.web_search` gets a single provider adapter; the builder picks the
  provider and records why in the PR.
- The thresholds in §5.7 (300 claims / 30 providers / AUC 0.60) and the
  10-point maximum weight.
- SEBI enforcement orders as the one new provider fact that counts toward the score.
