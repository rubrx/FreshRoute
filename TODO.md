# TODO — FreshRoute

Full phase-by-phase backlog. Move items to `PROGRESS.md` as they ship.

Legend: `[ ]` open · `[~]` in progress · `[x]` done (then move to PROGRESS.md)

## Hard gates

Three gates are binding — the code path is designed around them. See `CLAUDE.md` for the failure modes.

| Gate | When | Test |
|---|---|---|
| **1. Panel density** | End of week 2 | Do enough mandis report ≥ 60% of expected days? |
| **2. Cost model** | End of week 4 | Does `backend/cost/model.py` return itemized ₹/tonne with sourced state rates? |
| **3. Core done** | End of week 9 | Ingestion → forecasts → freshness → ranker → dashboard working end-to-end? |

---

## Phase 1 — Data foundation (weeks 1–2) · Owner: R

**🔒 Gate 1 at end:** Is the panel clean and dense enough to build on? Drop mandis reporting < 60% of days in the study window.

### 1.1 Project scaffolding
- [x] Directory structure (`backend/`, `data/`, `docs/`, `scripts/`)
- [x] `CLAUDE.md`, `PROGRESS.md`, `TODO.md`
- [x] `.gitignore`
- [x] `.env.example` with all required keys documented
- [x] `backend/pyproject.toml` with Phase 1 dependencies pinned
- [x] `README.md` — quickstart for teammates
- [ ] `git init` + initial commit (ask user before running)

### 1.2 Local infrastructure
- [x] `docker-compose.yml` with Postgres + TimescaleDB (`timescale/timescaledb:latest-pg16`)
- [x] Named volume for DB persistence
- [x] Healthcheck on the DB container
- [ ] `make up` / `make down` targets in a `Makefile` (or `scripts/dev.sh`)
- [ ] Verify container starts and `psql` connects

### 1.3 Database schema
- [x] Migration `001_init.sql` — extensions (timescaledb), schemas
- [x] Migration `002_reference.sql` — `commodities`, `states`, `markets` (mandis) tables
- [x] Migration `003_panel.sql` — `market_daily` hypertable (date, market_id, commodity_id, variety, min/modal/max price, arrival)
- [x] Migration `004_indices.sql` — indices on (commodity_id, date), (market_id, date)
- [x] `backend/db/connection.py` — SQLAlchemy engine + session factory
- [x] `backend/db/migrate.py` — apply pending migrations in order

### 1.4 Ingestion — data.gov.in fallback (Agmarknet REST API blocked by CAPTCHA)
- [x] Verify `agmarknet` PyPI package version + API surface — done 2026-09-08. Rewrote client for `agmarknet==0.2.2`
- [x] Discover AGMARKNET REST API CAPTCHA gate — see `docs/phase1-data-source-note.md`
- [x] `backend/ingestion/datagovin_client.py` — paginated snapshot fetcher (curl UA + client-side filter workaround)
- [x] `backend/ingestion/pull_datagovin.py` — orchestrates fetch → filter → normalize → upsert
- [x] `freshroute pull-datagovin` CLI command
- [x] End-to-end pull verified — 1,172 rows landed in `market_daily` on 2026-09-08
- [x] Land raw snapshots to `data/raw/datagovin/snapshot_{iso}.parquet`
- [x] `backend/ingestion/normalize.py` — extended aliases for data.gov.in column names; unit-guard added (Quintal → Tonne)
- [x] `backend/ingestion/agmarknet_client.py` + `backfill.py` + `daily.py` — kept in the tree, currently unusable pending Phase 1.5 CAPTCHA workaround
- [ ] **R:** Wire `pull-datagovin` into a daily cron / launchd job so history starts accumulating from Day 1
- [ ] **R (Phase 1.5):** land at least one community historical dump (Kaggle / GitHub) tagged `source='community-dump'`

### 1.5 Data quality
- [x] `backend/ingestion/quality.py` — reporting density per market, panel gaps, duplicate detection, unit anomalies
- [x] `freshroute quality --window-start … --window-end …` emits `docs/data-quality-report.md`
- [x] `docs/phase1-mandi-selection.md` — interim policy (Gate 1 deferred, not failed)
- [ ] **GATE 1 (2026-11-07):** re-run density check on 60-day accumulated panel. Prune mandis < 60 %, or expand state coverage if too few remain

---

## Phase 2 — Cost + freshness reference data (weeks 2–4)

**🔒 Gate 2 at end of week 4:** Cost model v1 must exist — the ranker literally cannot be written without it. ✅ CODE + SEED SHIPPED — validation open.

### 2.1 Shelf-life table (owner: M + T)
- [x] Download USDA AH-66 PDF (values transcribed inline — see notes)
- [x] Transcribe ~15 chosen commodities to `data/reference/shelf_life.csv` — 16 rows shipped
- [x] Document unit assumptions in `docs/shelf-life-notes.md`
- [ ] **T:** Field-validate SL_opt haircuts for Indian open-truck conditions; add `sl_field_haircut` column
- [ ] **M+T:** Cultivar-specific rows for Alphonso/Kesar mango, Ansal/Namdhari tomato if the data supports it

### 2.2 Cost model v1 (owner: T — hard week-4 deadline)
- [x] `data/reference/costs.csv` seeded for 10 states with source notes on each row
- [x] `data/reference/freight.csv` seeded with 5 truck sizes
- [x] `backend/cost/model.py` — `net_realization(...)` returns `CostBreakdown` dataclass with itemized ₹ lines
- [x] Unit tests for `cost/model.py` — 13 cases including invariants and reference-CSV guardrails
- [ ] **T:** Ground-truth the state cost rates against 2+ live trader / APMC contacts (Ludhiana, Azadpur, Nashik at minimum). Update the CSV row-by-row with sourced numbers

### 2.3 Seasonal arrival index (owner: M)
- [x] `backend/forecasting/seasonal.py` — AI + windowing + docs heatmap
- [x] Emit `data/processed/seasonal_index.parquet` via `freshroute seasonal`
- [x] Visual: heatmap per commodity × state × week → `docs/seasonal-calendar.md`
- [ ] **M:** Cross-check derived calendar against NHB Horticultural Statistics for ≥ 2 commodity × state combos (sanity only — note NHB caveats)
- [ ] **M:** Run against real backfilled data once Phase 1 backfill completes; sanity-check for expected patterns (tomato Nov–Jan glut, onion Feb–Apr + Nov–Dec)

### 2.4 OSRM + mandi geocoding (owner: R)
- [x] `docker-compose.yml` — OSRM services added under `osrm-bootstrap` and `osrm` profiles
- [x] `scripts/osrm_bootstrap.sh` — one-shot Geofabrik download + MLD pipeline
- [x] `backend/ingestion/geocode.py` — polite Nominatim client with CSV cache
- [x] `backend/freshness/distance_matrix.py` — OSRM pair-wise routes with polyline, parquet cache
- [x] `freshroute geocode` and `freshroute distances` CLI commands
- [ ] **R:** Actually run `scripts/osrm_bootstrap.sh` (~30–60 min, ~10 GB disk)
- [ ] **R:** Run `freshroute geocode` after Phase 1 backfill so `markets` is populated
- [ ] **R:** Compute the distance matrix for the mandis retained by the Phase 1 quality gate

---

## Phase 3 — Forecasting (weeks 3, 5–7) · Owner: M

### 3.1 Backtest harness (week 3 — before any model)
- [ ] `backend/forecasting/backtest.py` — rolling-origin evaluation, configurable horizon 1..7
- [ ] Baselines: naive (last known), seasonal-naive (same weekday last year), 7-day MA
- [ ] Metrics: MAE, MAPE, pinball loss per quantile
- [ ] Report emitter: `docs/backtest-baseline.md`
- [ ] **Rule:** no model ships without beating all three baselines

### 3.2 Price forecaster (weeks 5–6)
- [ ] Feature engineering: price + arrival lags, week-of-year, festival flags, monsoon flag, district/state aggregates, neighbouring-mandi lags, weather covariates
- [ ] LightGBM quantile objective, one model per quantile (P10, P50, P90)
- [ ] Global model across mandis with market_id as categorical
- [ ] Missing-data handling: masking, gap-aware lags, imputation strategy (write this up — real contribution)
- [ ] Persist trained models to `data/models/price_lgbm_p{10,50,90}.pkl`
- [ ] Backtest report vs baselines → `docs/price-forecast-results.md`

### 3.3 Arrival forecaster (weeks 6–7)
- [ ] Same feature family, target = arrival volume
- [ ] Feeds glut early warning
- [ ] Backtest report → `docs/arrival-forecast-results.md`

### 3.4 Anomaly + abstention
- [ ] Anomaly detector on raw feed (unit errors, 10× price typos) — flags before ingest
- [ ] Conformal prediction intervals → `abstain` when P90 − P10 > threshold

---

## Phase 4 — Freshness engine service (weeks 5–6) · Owner: R

- [ ] `backend/freshness/shelf_life.py` — loader for shelf_life.csv, per-commodity SL_opt/T_opt/Q10 lookup
- [ ] `backend/freshness/weather.py` — Open-Meteo client, hourly temperature along a polyline, cached per (route_hash, dispatch_date)
- [ ] `backend/freshness/decay.py` — Q₁₀ decay integrator: `rate(T) = rate_opt · Q10 ^ ((T − T_opt)/10)`, integrate over route segments + expected mandi dwell time
- [ ] `backend/freshness/service.py` — `remaining_life(commodity, origin, destination, dispatch_ts) → R ∈ [0,1]` with breakdown
- [ ] Unit tests with known synthetic routes
- [ ] Feasibility filter: `R < R_min` (default 0.35) → destination dropped with reason string

---

## Phase 5 — Decision engine + dashboard (weeks 7–9)

**⚠️ Not a price-display app.** Every UI surface must justify itself against the standard: does this help the user make a *decision* they could not make from an Agmarknet dashboard? If no, cut it. The ranked destination cards with the itemized ₹ breakdown + feasibility reason are the centrepiece — everything else is context.

**🔒 Gate 3 at end of week 9:** Ingestion → forecasts → freshness → ranker → dashboard working end-to-end? Only if yes → touch stretch features S1–S5.

### 5.1 Decision engine (owner: R + M)
- [ ] `backend/decision/ranker.py` — combines forecast P50 + freshness R + cost model → net ₹/tonne per candidate mandi
- [ ] Grade discount `q(R)` calibrated against intra-market min/modal/max spread
- [ ] Returns ranked list with P10 downside, itemized breakdown, feasibility reason if excluded
- [ ] `backend/api/main.py` — FastAPI, endpoint `POST /recommend` accepts (commodity, origin, quantity_tonnes, dispatch_ts)
- [ ] Unit tests: feasibility filter runs *before* the ranker; infeasible destinations never appear in output

### 5.2 Dashboard (owner: R)
- [ ] Framework decision (Next.js vs plain React + Vite) — document in `docs/dashboard-arch.md`
- [ ] Mobile-first responsive layout
- [ ] **Primary surface:** ranked destination cards with itemized ₹ breakdown + feasibility reason
- [ ] Mandi map view (context, not the primary surface)
- [ ] Price history chart per (commodity, mandi) (context)
- [ ] Seasonal calendar heatmap — glut/lean windows per (commodity, state) from `seasonal_index.parquet`
- [ ] Freshness overlay: on any destination, show the shelf-life budget consumed along the route + expected mandi dwell, so the trader can see *why* something is infeasible
- [ ] Glut warnings panel
- [ ] Hindi + English toggle

---

## Phase 6 — Alerts + counterfactual ledger (weeks 9–11)

### 6.1 Alerts (owner: R)
- [ ] Twilio trial or Gupshup sandbox account
- [ ] `backend/alerts/dispatcher.py` — sends WhatsApp/SMS, Hindi + English templates
- [ ] Triggers: glut early warning, forecast crash, favourable window opens
- [ ] Opt-in preference storage (per trader)

### 6.2 Counterfactual ledger (owner: M + R)
- [ ] Persist every recommendation with timestamp + inputs + full breakdown
- [ ] Nightly job: score each recommendation against realized prices
- [ ] Report: cumulative ₹/tonne uplift vs (a) nearest mandi baseline, (b) historical default mandi baseline
- [ ] Emit `docs/counterfactual-90day.md`

### 6.3 Abstention integration
- [ ] Wire conformal intervals into ranker → "no confident edge, sell local" surface in UI

---

## Phase 7 — Field validation + report (weeks 11–12)

### 7.0 Buyer segment probe — start early (owner: T, week 4 onward, not week 11)
- [ ] 3–5 exploratory calls in weeks 4–6: is the buyer a **trader**, an **FPO**, an **agri-B2B platform**, or a **state agri department**? Do not defer this to month 6 — it changes what the dashboard needs to look like
- [ ] Short writeup → `docs/buyer-segment-probe.md` before Phase 5 UI decisions freeze

### 7.1 Field validation (owner: T)
- [ ] 12–15 trader / FPO / commission agent interviews (Una, Nurpur, Ludhiana, Solan, Delhi Azadpur)
- [ ] Show 10–15 traders last month's recommendations vs what they actually did — record reactions
- [ ] Validate `q(R)` grade-discount curve against real trader experience
- [ ] Validate AH-66 shelf-life haircuts for Indian open-truck conditions → add `sl_field_haircut` column to `shelf_life.csv`
- [ ] Final buyer segment writeup (converts the week-4–6 probe into a business case)
- [ ] Writeup → `docs/field-validation.md`

### 7.2 Thesis + defense
- [ ] Data-engineering writeup on Agmarknet panel quirks + handling
- [ ] Forecast skill report vs baselines
- [ ] **The line:** 90-day ₹/tonne uplift + within-shelf-life % vs baseline policies
- [ ] Business case: buyer segments, pricing, cost-benefit, competitive gap
- [ ] Risk register (quantified)
- [ ] Thesis document
- [ ] Defense deck
- [ ] Live demo checklist

---

## Stretch (only if core done by week 9)

- [ ] S1 — Hold-vs-sell with cold storage
- [ ] S2 — Split-lot allocation across mandis
- [ ] S3 — Procurement mode (cheapest landed cost for buyers)
- [ ] S4 — Harvest wave map (cross-correlate arrival peaks)
- [ ] S5 — FPO truck-fill (aggregate small lots)
