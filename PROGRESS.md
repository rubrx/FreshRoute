# PROGRESS — FreshRoute

Append-only log of completed work per phase. New entries go at the top of each phase section.

---

## Planning + docs

### 2026-09-06 — Origin + tech-stack rationale captured

- `docs/proposal.md` — full capstone proposal covering the 28-idea shortlist, why the constraints killed the initial COD/RTO pick, why mandi routing survives, the framing insight (arbitrage 40–100% >> forecast error ~15%), the four differentiators, architecture, data sources, ML approach, team roles, 12-week timeline with hard gates, evaluation, risks, Amazon Last Mile runner-up rejection, and the single defense sentence
- `docs/tech-stack.md` — every component with rationale + rejected alternatives (why LightGBM not deep learning, why Postgres+Timescale not ClickHouse, why OSRM-MLD not Google Maps, why plain SQL migrations not Alembic, etc.)
- `CLAUDE.md` — added "Origin & key insight" section, "Hard gates" table (weeks 2, 4, 9), 3 new ground rules (not a display app · freshness is a hard constraint · don't hard-code the crop calendar), and expanded "Not in scope" list
- `TODO.md` — added top-of-file hard-gates callout, tagged Gate 1/2/3 in Phase 1/2/5 headers, added "not a display app" warning to Phase 5, moved buyer-segment probe from Phase 7 (week 11) to Phase 7.0 (week 4–6 exploratory) so the buyer question is answered *before* the UI freezes
- `README.md` — reorganized with a "start here" doc index

No code changes.

---

## Phase 1 — Data foundation

### 2026-09-08 — End-to-end pipeline verified against real data (data.gov.in fallback)

**Environment brought up**
- Docker Desktop + `docker compose up -d db` — Postgres 16 + TimescaleDB healthy on port 5433
- `python3.13 -m venv .venv` + `pip install -e backend` — all pinned deps resolve on Python 3.13 (pyarrow 25.0.1, pandas 3.0.5, sqlalchemy 2.0.52, agmarknet 0.2.2)
- `python -m backend.cli migrate` — all 4 migrations applied cleanly; `\dt` confirms 5 tables

**Data source pivot** (full writeup in `docs/phase1-data-source-note.md`)
- Verified the actual return shape of `agmarknet==0.2.2` on a live pull — the SDK uses a REST API, not the assumed scraper, so `backend/ingestion/agmarknet_client.py` was rewritten to use the `Agmarknet` class + `.report(...)` and the version pin was loosened to `>=0.2.2,<1.0`. Column aliases in `backend/ingestion/normalize.py` extended for `cmdt_name`, `model_price` (SDK's "model" ≠ "modal" typo), `arrival_qty`, `variety_name`, and a new unit-guard converts Quintal→Tonne when the row's `unit_name_arrival` says so
- **Discovered a hard blocker:** the AGMARKNET REST API now returns `TOKEN_OR_CAPTCHA_REQUIRED` on every request. Automation against the primary source is currently impossible without a CAPTCHA solver (violates the free-data constraint)
- Pivoted to data.gov.in resource `9ef84268-d588-465a-a308-a864a43d0070` — CLAUDE.md ground rule 4 already anticipated this fallback. Two production quirks caught the hard way and documented at the top of the client:
    - Default `python-requests` / `httpx` User-Agents get silently rate-limited (60s timeouts, 0 bytes). A `curl/8.7.1` UA returns 200 in 0.6s
    - Server-side filters like `filters[state]=Maharashtra` time out reliably; the working pattern is to pull the full ~10k-row snapshot and filter client-side

**New ingestion path**
- `backend/ingestion/datagovin_client.py` — paginated snapshot fetcher (1000/page, curl-like UA, tenacity retry). `SnapshotFilter` + `apply_filter` do client-side filtering. `dump_raw` persists to `data/raw/datagovin/snapshot_{iso}.parquet` for offline reuse
- `backend/ingestion/pull_datagovin.py` — orchestrates fetch → filter → normalize → upsert (source tagged `datagovin`)
- `backend/cli.py` — new `freshroute pull-datagovin --commodities … --states …` command

**End-to-end verified pull (2026-09-08 snapshot)**
- 10,000 raw rows in 10.7s
- 1,178 rows matched Tomato/Onion/Potato/Banana
- **1,172 rows landed in `market_daily`** (6 dropped by normalize for missing keys — expected)
- **23 states, 417 markets, 4 commodities** auto-registered from a single snapshot
- Signal check: Tomato in Uttar Pradesh shows Fatehpur APMC ₹2,587/qtl vs Varanasi APMC ₹1,500/qtl — a **72 % same-day spread**, exactly the arbitrage-visibility premise the capstone is built on. Visible on Day 1

**Quality report + Gate 1 decision**
- `docs/data-quality-report.md` — regenerated with `freshroute quality --window-start 2026-09-08 --window-end 2026-09-08`. 1,152 (market × commodity) rows shown at 100 % density on this 1-day window
- `docs/phase1-mandi-selection.md` — Gate 1 deferred (not failed): the density test presumes multi-year data; we have 1 day. Formal re-run scheduled for **Day 60 (2026-11-07)**. Interim policy: keep every reporting mandi, prune only after accumulation
- `docs/phase1-data-source-note.md` — full writeup of the pivot as a defensible thesis chapter ("government open-data pipelines drift; the largest engineering risk is source freshness, not modelling")

### 2026-09-05 — Phase 1 scaffolding shipped

**Project structure**
- Directory tree: `backend/{ingestion,db/migrations,config}`, `data/{raw,processed,reference}`, `docs/`, `scripts/`
- Tracking files: `CLAUDE.md` (session orientation), `PROGRESS.md` (this file), `TODO.md` (phase backlog)
- `README.md` — quickstart for teammates
- `.gitignore` — excludes `.env`, `data/raw/**`, `data/processed/**`, model artifacts, Python caches
- `.env.example` — documents all required secrets (data.gov.in key, DB URL, Twilio placeholders for later phases)

**Local infrastructure**
- `docker-compose.yml` — Postgres 16 + TimescaleDB (`timescale/timescaledb:latest-pg16`), named volume `freshroute_db`, healthcheck via `pg_isready`, port 5433 to avoid clashing with a local Postgres

**Backend package**
- `backend/pyproject.toml` — Python 3.11+, pinned deps: `agmarknet`, `sqlalchemy`, `psycopg2-binary`, `pandas`, `pyarrow`, `python-dotenv`, `pydantic-settings`, `typer`, `httpx`, `tenacity`, `structlog`
- `backend/config/settings.py` — `pydantic-settings` loader for env vars
- `backend/db/connection.py` — SQLAlchemy engine factory
- `backend/db/migrate.py` — plain-SQL migration runner (numbered files applied in order, tracked in `schema_migrations` table)

**Database schema (migrations)**
- `001_init.sql` — enables `timescaledb` extension, creates `schema_migrations` bookkeeping table
- `002_reference.sql` — `commodities`, `states`, `markets` (mandis with lat/lon columns for Phase 2 geocoding)
- `003_panel.sql` — `market_daily` hypertable partitioned on `date`, columns: date, market_id, commodity_id, variety, min/modal/max price, arrival_tonnes, source, ingested_at. Unique constraint on (date, market_id, commodity_id, variety) for idempotent upserts
- `004_indices.sql` — btree on `(commodity_id, date DESC)` and `(market_id, date DESC)` for fast lookback queries

**Ingestion service**
- `backend/ingestion/agmarknet_client.py` — retry-wrapped client with tenacity exponential backoff
- `backend/ingestion/normalize.py` — DD/MM/YYYY → ISO date, string→numeric coercion, dedupe on natural key, variety-collision handling
- `backend/ingestion/backfill.py` — year-chunked historical pull, resumable via a `state.json` cursor per (state, commodity)
- `backend/ingestion/daily.py` — incremental pull for the last N days (default 7 to catch late reporters)
- `backend/ingestion/quality.py` — reporting-density calculator, gap detection, unit-anomaly flagger (10× price typos), duplicate collision report
- `backend/cli.py` — typer CLI: `migrate`, `backfill`, `daily`, `quality`

### Outstanding for Phase 1 (see TODO.md §1.4–1.5)
- Verify the actual return shape of the `agmarknet` PyPI package on a live pull (may require a follow-up patch to the client if the SDK signature differs from what the plan assumes)
- Run the full backfill for the chosen 4 commodities × 3 states
- Emit the data-quality report to `docs/data-quality-report.md`
- Make the week-2 gate call: is the panel dense enough?

---

## Phase 2 — Cost + freshness reference data

### 2026-09-06 — Phase 2 scaffolding shipped

**Shelf-life reference (§2.1)**
- `data/reference/shelf_life.csv` — 16 commodities transcribed from USDA AH-66 with columns: `commodity, t_opt_c, rh_opt_pct, sl_opt_days, q10, chilling_injury_floor_c, ethylene_sensitive, ethylene_producer, category, notes`
- `docs/shelf-life-notes.md` — column semantics, range→midpoint conversion rule, Q₁₀ assignment logic (2.0 for dry bulbs, 2.5 default, 3.0 for high-respiration), chilling-injury caveat, four Indian-context caveats (open-truck heat, cultivar variation, pre-cooling absent, onion/potato dominance), and cross-check sources to hit in Phase 7

**Cost model v1 (§2.2)**
- `data/reference/costs.csv` — 10 states seeded with APMC commission %, cess %, entry fee ₹/tonne, labour ₹/tonne, weighment ₹/tonne. Every row carries a `notes` column identifying the source APMC act / reference mandi
- `data/reference/freight.csv` — 5 truck sizes (3, 7, 10, 16, 25 tonnes) with `rs_per_km_base`, `diesel_price_reference_rs_per_l`, `fixed_loading_rs`
- `backend/cost/model.py` — pure `net_realization(...)` returning a `CostBreakdown` dataclass with every line item in ₹, plus `pick_truck()` picking the smallest truck that fits (multi-trip when the load exceeds any single truck). Diesel-linked freight scales linearly via a 60% sensitivity coefficient
- `backend/cost/tests/test_model.py` — 13 pytest cases covering deduction-sum invariance, ₹/quintal → ₹/tonne conversion, APMC as % of gross, zero-distance still incurring fixed loading, diesel scaling, multi-trip cost, unknown state raising `KeyError`, negative-input rejection, and reference-CSV guardrails (rate ranges, monotonic truck sizing)

**Seasonal arrival index (§2.3)**
- `backend/forecasting/seasonal.py` — computes `AI(commodity, state, iso_week) = median arrivals in week / weekly baseline` from `market_daily`. Filters to `is_active` markets by default and drops (commodity, state) combos with fewer than `min_years` distinct years covered. Emits `data/processed/seasonal_index.parquet` with a `window` column labeled `glut` (AI ≥ 1.5), `lean` (AI ≤ 0.6), or `normal`
- `render_markdown_heatmap()` emits a 52-column ISO-week ASCII heatmap per commodity × state → `docs/seasonal-calendar.md` (uses `▲` / `▼` / `·` symbols)

**OSRM (§2.4)**
- `docker-compose.yml` extended with two OSRM services behind compose profiles: `osrm-preprocess` (one-shot, profile `osrm-bootstrap`) and `osrm` (routing server on port 5000, profile `osrm`). Neither starts by default
- `scripts/osrm_bootstrap.sh` — downloads the Geofabrik India extract (~1.4 GB), runs the MLD pipeline (extract → partition → customize), and idempotently skips if artifacts already exist. Preprocessed files land in `./data/osrm/`
- `.gitignore` updated to exclude `data/osrm/`

**Geocoding (§2.4)**
- `backend/ingestion/geocode.py` — polite Nominatim client (≥ 1.1 s between requests, dedicated User-Agent), tries 4 query variants per mandi (`X mandi, District, State, India` etc.), caches to `data/reference/mandi_geocodes.csv`, updates `markets.latitude/longitude/geocode_source`. Cache format keyed on `market_id` and diffable in review

**Distance matrix (§2.4)**
- `backend/freshness/distance_matrix.py` — calls OSRM `/route/v1/driving` per pair (not the `/table` service — we also need the polyline for the Phase 4 freshness engine to sample weather along the route). Cache written to `data/processed/distance_matrix.parquet` with columns `origin_id, origin_lat, origin_lon, dest_id, dest_lat, dest_lon, distance_km, duration_hours, polyline_geojson, computed_at`. `compute_matrix(origins, dests)` builds the cross-product and skips cached pairs unless `force=True`

**CLI additions**
- `freshroute seasonal` — compute + write parquet + docs heatmap
- `freshroute geocode [--force]` — resolve mandi coords via Nominatim
- `freshroute distances [--origins IDS] [--dests IDS] [--no-polyline] [--force]` — populate the distance matrix

### Outstanding for Phase 2
- Tanishq: validate the seeded state cost rates against a live trader / APMC contact and update `costs.csv`. Numbers ship-safe now but need per-mandi refinement in Ludhiana / Azadpur / Nashik before the Phase 7 defense
- Tanishq: field-validate shelf-life haircuts and add `sl_field_haircut` column when data lands
- Monish: cross-check the derived seasonal index against NHB Horticultural Statistics at a Glance for at least 2 commodity × state combinations (sanity only — note NHB caveats)
- Rubrangso: run `scripts/osrm_bootstrap.sh` (~30–60 min) and then `freshroute geocode` and `freshroute distances` after Phase 1 backfill completes
- Confirm that `seasonal_index.parquet` produces a plausible calendar for tomato/onion once real data is loaded — expected patterns: tomato glut in Nov–Jan, onion glut in Feb–Apr and Nov–Dec (kharif + rabi)

---

## Phase 3 — Forecasting

_Not started._

---

## Phase 4 — Freshness engine service

_Not started._

---

## Phase 5 — Decision engine + dashboard

_Not started._

---

## Phase 6 — Alerts + counterfactual ledger

_Not started._

---

## Phase 7 — Field validation + report

_Not started._
