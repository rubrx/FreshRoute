# Tech stack — FreshRoute

Every choice below is deliberate. This doc explains **why** each component was picked and **what was rejected** in its place, so the choices are auditable in the thesis defense.

Two constraints override everything:

1. **100% free public data / free software** — no paid APIs, no proprietary SDKs.
2. **12-week build with a 3-person team** — anything requiring more than one week to stand up needs a hard justification.

---

## Language & runtime

| Choice | Rationale |
|---|---|
| **Python 3.11+** | Matches Monish's stack (pandas / scikit-learn / LightGBM). The `agmarknet` SDK is Python. `structlog`, `typer`, `pydantic-settings`, `httpx` are all first-class. |
| Rejected: Go / Rust for the API | Nothing in this system is throughput-bound. Consistent-language project is easier for a 3-person team. |
| Rejected: Julia for the ML side | LightGBM's most mature bindings are Python. Julia would fragment the team. |

## Package management & project layout

| Choice | Rationale |
|---|---|
| **`pyproject.toml` with setuptools + `pip install -e .`** | Standard, no extra tooling to install. Editable install = fast iteration. |
| Rejected: Poetry / uv | Add a dependency-manager to onboard. `pip` + `pyproject.toml` is enough for a 3-person team. Revisit if the dep graph explodes. |
| Rejected: conda | Heavier install; no CUDA in scope (no deep learning). |

## Database

| Choice | Rationale |
|---|---|
| **Postgres 16 + TimescaleDB** | Native time-series partitioning (`market_daily` hypertable, 1-month chunks). Standard SQL access from pandas. No new query language. Handles the panel (~few million rows over the study window) comfortably on a laptop. |
| Rejected: ClickHouse | Query language divergence and extra ops for a scale we do not need. |
| Rejected: SQLite / DuckDB | No concurrent writers; painful for the ingestion service + notebooks + API talking to the same store. DuckDB is used *ad hoc* for one-off parquet analysis. |
| Rejected: managed cloud DB | "100% free" constraint. Local Postgres in Docker is enough. |

**Access:** SQLAlchemy 2.0 (sync) + `psycopg2-binary`. Sync is enough for a batch pipeline; the recommendation API's throughput needs are modest (per-request query on cached forecasts). No `asyncpg` for now.

**Migrations:** plain SQL files (`backend/db/migrations/NNN_*.sql`) applied by a small custom runner tracked in `schema_migrations`. Simpler than Alembic for a fixed schema; every migration is diffable in review.

## Ingestion

| Choice | Rationale |
|---|---|
| **`agmarknet` PyPI SDK** as the primary source | Only free source that carries **arrival volumes**, which is what predicts a glut. Auto-chunks long ranges by year. |
| **`data.gov.in` NDSAP daily API** as a secondary live feed | Prices-only. Use only for the "today's price" surface, never for historical. |
| **`httpx` + `tenacity`** | Modern HTTP, exponential-backoff retries with typed exception matching. Isolate the SDK call in one wrapper so a version-change ripples through one file only. |
| **Raw parquet dumps** at `data/raw/agmarknet/{year}/{state}/{commodity}.parquet` | Offline reproducibility; DB rebuilds can source from parquet without re-hitting Agmarknet. |
| **State cursor** at `data/raw/agmarknet/state.json` | Resumable backfill without an external orchestrator. |
| Rejected: Airflow / Prefect / Dagster | Overkill for a daily cron + a resumable backfill. Ops tax outweighs the reliability benefit at this scale. |
| Rejected: Kafka / streaming | Batch daily is fine; Agmarknet itself publishes daily. |

**Normalization:** lenient column alias mapping (`normalize.py`) so SDK-version changes do not require touching downstream code. `DD/MM/YYYY → ISO`, unit-anomaly filtering (10× typo detector in `quality.py`), dedupe on the natural key `(date, market, commodity, variety)`.

**Idempotent upsert:** `ON CONFLICT (date, market_id, commodity_id, variety) DO UPDATE`. Rerunning the backfill is safe.

## Reference data

| Choice | Rationale |
|---|---|
| **CSVs in `data/reference/` — versioned** | Small, human-editable, diffable. Every ingestion of these files is a code review. |
| `shelf_life.csv` (16 rows) | Transcribed from USDA AH-66 with midpoint conversion. Every column semantically documented in `docs/shelf-life-notes.md`. |
| `costs.csv` (10 rows, one per state) | APMC commission, cess, entry fee, labour, weighment. Each row carries a `notes` field identifying the reference APMC / source act. |
| `freight.csv` (5 truck sizes) | ₹/km base + diesel-linked scaling coefficient. |
| `mandi_geocodes.csv` | Nominatim results cached — mandis do not move. |

## Routing (Phase 2 §2.4)

| Choice | Rationale |
|---|---|
| **OSRM (self-hosted) on Geofabrik India OSM extract** | Free forever, no rate limits, offline. Ships in a Docker container. |
| **MLD algorithm** (`osrm-extract` → `osrm-partition` → `osrm-customize`) | Smaller RAM footprint than CH (contraction hierarchies), acceptable query latency. Preprocessing is a one-shot script. |
| Rejected: Google Maps Distance Matrix API | Paid past the free tier; would blow the "free data" constraint. |
| Rejected: OpenRouteService cloud | Free tier is rate-limited; self-hosted OSRM has no such cap. |

**Distance matrix caching:** `data/processed/distance_matrix.parquet` — pair-wise routes with the encoded polyline (needed for Phase 4 weather sampling along the route, not just distance/duration).

## Geocoding (Phase 2 §2.4)

| Choice | Rationale |
|---|---|
| **Nominatim public server** with strict polite-usage compliance | Free; sufficient for one-time geocode of ~100 mandis. |
| Rate limit ≥ 1.1 s between requests, identifying User-Agent | Nominatim usage policy. Cached locally — never re-hit. |
| Escape hatch: self-host Nominatim from the same OSM extract as OSRM | If we outgrow the public tier, `NOMINATIM_BASE_URL` is one env-var flip. |

## Weather (Phase 4)

| Choice | Rationale |
|---|---|
| **Open-Meteo** — free, no key, non-commercial ok | Historical archive + forecast, hourly temp/humidity/rain. |
| Sample hourly along the OSRM polyline | Freshness budget is a route-and-time integral, not a two-endpoint average. |
| Rejected: OpenWeather / VisualCrossing paid tiers | Paid; not needed. |

## Forecasting (Phase 3)

| Choice | Rationale |
|---|---|
| **LightGBM** with quantile objective (one model per quantile P10 / P50 / P90) | Best-in-class on tabular time-series; matches Monish's stack. Handles categorical `market_id` natively. |
| **Global model** with `market_id` as a categorical feature | Amortizes learning across mandis; a per-mandi model would starve on sparse markets. |
| Rejected: Prophet / statsforecast | Prophet is fine for seasonality-only; loses to LightGBM once we add arrival lags, weather, and neighbouring-mandi features. |
| Rejected: DeepAR / TFT | Deep learning overhead is not justified at this data density. Reproducibility and training cost are worse. |
| Rejected: XGBoost | Roughly equivalent; LightGBM is what Monish already uses. |
| **Rolling-origin backtest** with baselines (naive, seasonal-naive, 7-day MA) shipped **before** any model | Rule: no model ships without beating all three. |
| **Conformal prediction** for abstention | "No confident edge — sell local" when P90 − P10 exceeds a threshold. |

## Freshness engine (Phase 4)

| Choice | Rationale |
|---|---|
| **Analytical Q₁₀ decay** — no ML | The physics of respiration is well-modeled by `rate(T) = rate_opt × Q10 ^ ((T − T_opt)/10)`. Q₁₀ is per-commodity in `shelf_life.csv`. A learned model here would be noise-fitting. |
| Integrate along route segments + mandi dwell | Produce rots in the auction queue too — this is what most implementations forget. |
| Two outputs — **hard filter** (`R < R_min` → drop) and **soft discount** (`P_eff = P̂ × q(R)`) | Filter runs before ranking; discount runs after. |
| Grade-discount `q(R)` calibrated against intra-market min/modal/max spread | Grade is unobservable in Agmarknet — spread is the best free proxy. Documented as an assumption, validated with traders in Phase 7. |

## Decision engine (Phase 5)

| Choice | Rationale |
|---|---|
| **Pure Python module** — deterministic given forecasts + freshness + costs | Testable, replayable for the counterfactual ledger. |
| Rank by P50 of net realization, display P10 as downside | Downside is what a trader cares about most. |
| Feasibility filter runs **before** the ranker | Never rank a destination the produce cannot reach alive. |

## Serving

| Choice | Rationale |
|---|---|
| **FastAPI** for the recommendation API | Async ergonomics, OpenAPI schema out of the box, pydantic validation matches our config. |
| Nightly batch scoring writes to Postgres for dashboard read paths | Avoids online model calls on the trader's phone. |
| Rejected: Django REST | Overkill; no admin panel need. |
| Rejected: Flask | pydantic + async support in FastAPI is materially better. |

## Frontend (Phase 5) — framework decision deferred

Locked-in requirements:
- Mobile-first (traders check on phones).
- Hindi + English toggle.
- Mandi map, price history chart, ranked destination cards with itemized ₹ breakdown, seasonal heatmap, glut warnings.

Front-runners (decide at start of Phase 5, document in `docs/dashboard-arch.md`):

| Option | Pros | Cons |
|---|---|---|
| **Next.js (App Router)** | SSR, good mobile performance, mature. | More build config. |
| **React + Vite** | Minimal build, fast dev loop. | No SSR. Fine for a dashboard behind auth. |

Not chosen: SvelteKit / Vue — no team familiarity.

**CSS:** design tokens in CSS custom properties. Tailwind if we adopt it, but it is not a hard requirement — the design has to look intentional, not template-y (see `web/design-quality.md`).

## Alerts (Phase 6)

| Choice | Rationale |
|---|---|
| **Twilio trial** (WhatsApp Business API sandbox) or **Gupshup sandbox** | Free tiers cover the demo scale. |
| Hindi + English templates | Non-negotiable for the target user. |
| Rejected: SMS-only | Traders check WhatsApp far more than SMS. |

## Counterfactual ledger

| Choice | Rationale |
|---|---|
| **Postgres table** — every recommendation persisted with inputs + full breakdown | Nightly scoring against realized prices produces the ₹/tonne uplift number, which is the defense line. |
| Rejected: separate ledger DB | Same store keeps the dashboard's read path simple. |

## Deploy

| Choice | Rationale |
|---|---|
| **Docker Compose** on a single host | Matches `buildplan.md §7`. Everything (DB, OSRM, API, dashboard, cron) is one file. |
| Named volume for Postgres, bind mount for OSRM preprocessed artifacts | OSRM data is host-visible so rebuilds do not require rebuilding the container. |
| Basic auth + multi-tenant (trader / FPO scoping) | Enough for the field-validation phase; no need for OAuth infrastructure. |
| Rejected: Kubernetes | 3-person capstone, single-host deployment. |
| Rejected: cloud PaaS | "Free data" and "free software" constraints. |

## Dev tooling

| Tool | Purpose |
|---|---|
| **`pytest` + `pytest-cov`** | Tests. 80%+ coverage target on business-logic modules (`cost/`, `freshness/`, `decision/`). |
| **`ruff`** | Lint + format. |
| **`structlog`** | Key-value logs, JSON-ready. Trivial to ingest into any observability tool later. |
| **`typer`** | CLI for `migrate` / `backfill` / `daily` / `quality` / `seasonal` / `geocode` / `distances`. |
| **`pydantic-settings`** | `.env` → typed config. Fails fast on missing required values. |
| **`.env.example`** | Documents every secret required, per phase. |
| **Plain SQL migrations** | Numbered, reviewable, no ORM state coupling. |

Not adopted (yet):
- pre-commit hooks — would add if the team grows beyond three or the CI story tightens.
- Alembic — overkill for a schema of this size.
- MLflow — a simple file-naming convention (`data/models/{model}_p{quantile}_v{n}.pkl`) is enough.
- dbt — no data-warehouse-scale transformations.
- Feature store — LightGBM reads from parquet + Postgres directly.

## Observability

| Choice | Rationale |
|---|---|
| **structlog** with JSON output when `ENV=prod`, key-value when `ENV=dev` | Every ingestion / scoring / decision call is logged with correlation keys (`market_id`, `commodity_id`, `date`). |
| **Ingestion completeness metric** as a KPI dashboard row | % of expected market-days captured. |
| **p95 recommendation latency** as a KPI dashboard row | System SLO. |
| Not adopted: Prometheus / Grafana / Sentry | Deferred. Add if the operational scale demands it. |

---

## Summary: the whole stack, one page

```
┌─ Language ────────────────────────────────────────────────────┐
│  Python 3.11+                                                 │
├─ Data & pipelines ────────────────────────────────────────────┤
│  pandas · pyarrow · numpy                                     │
│  agmarknet (PyPI) · httpx + tenacity · structlog              │
│  SQLAlchemy 2.0 · psycopg2                                    │
│  Postgres 16 + TimescaleDB (hypertable, 1-month chunks)       │
│  Plain SQL migrations, numbered                               │
├─ Config & CLI ────────────────────────────────────────────────┤
│  pydantic-settings · python-dotenv · Typer                    │
├─ Routing & geocoding ─────────────────────────────────────────┤
│  OSRM self-hosted (MLD) on Geofabrik India extract            │
│  Nominatim public (polite) — fallback: self-host              │
├─ Weather ─────────────────────────────────────────────────────┤
│  Open-Meteo (free, no key)                                    │
├─ ML ──────────────────────────────────────────────────────────┤
│  LightGBM (quantile P10/P50/P90) · scikit-learn               │
│  Rolling-origin backtest · baselines: naive, seasonal, MA     │
│  Conformal prediction for abstention                          │
├─ Physics ─────────────────────────────────────────────────────┤
│  Q₁₀ decay integrator (analytical, no ML)                     │
├─ Serving ─────────────────────────────────────────────────────┤
│  FastAPI (recommendation API)                                 │
│  Nightly batch scoring → Postgres                             │
├─ Frontend ────────────────────────────────────────────────────┤
│  Next.js or React + Vite (decided at Phase 5)                 │
│  Mobile-first · Hindi + English                               │
├─ Alerts ──────────────────────────────────────────────────────┤
│  Twilio / Gupshup sandbox — WhatsApp + SMS                    │
├─ Testing & lint ──────────────────────────────────────────────┤
│  pytest · pytest-cov · ruff                                   │
├─ Deploy ──────────────────────────────────────────────────────┤
│  Docker Compose · named DB volume · bind-mount OSRM data      │
└───────────────────────────────────────────────────────────────┘
```
