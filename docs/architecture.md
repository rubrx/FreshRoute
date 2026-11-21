# FreshRoute — Architecture

## What it does

Ranks candidate mandis by expected net ₹/tonne after spoilage loss, freight, and market charges. The core insight: same-day price spread between mandis (40–100%) dwarfs realistic 1–7 day forecast error (~15%), so value comes from **arbitrage visibility + cost-netting + spoilage feasibility**, not forecast precision.

The defense line: _"Over 90 days of historical backtesting across N mandis, FreshRoute recommendations earned ₹X more per tonne than the default policy, while keeping Y% of consignments within shelf life vs Z% for the baseline."_

Team: Rubrangso (full-stack + infra), Monish (AI/ML), Tanishq (management/ops). IIIT Una B.Tech IT capstone, 2023–27.

---

## Data flow

```
Agmarknet (18yr history)          data.gov.in (live daily)
         ↓                                  ↓
   ingestion/                          ingestion/
   agmarknet_client.py            datagovin_client.py
         ↓                                  ↓
   normalize → quality → upsert → market_daily (TimescaleDB)
                                           ↓
                              decision/recommender.py
                                    ↙         ↘
              cost/model.py                decision/spoilage.py
              (freight + APMC)             (Q10 decay)
                                    ↘         ↙
                               api/routers/recommend.py
                                           ↓
                                   Next.js frontend
```

---

## Modules

| Module | What it does |
|---|---|
| `backend/ingestion/` | Pulls Agmarknet historical + data.gov.in daily → TimescaleDB |
| `backend/cost/` | Converts ₹/quintal quote to net ₹/tonne after freight, APMC, cess, entry fee, labour, weighment |
| `backend/decision/` | Recommender: resolves geocoords, estimates spoilage, ranks mandis by net ₹/tonne |
| `backend/analysis/` | Market intelligence: price percentile rank, vs-state-median signals |
| `backend/freshness/` | Distance matrix via OSRM (Phase 4 will add Open-Meteo weather profile) |
| `backend/forecasting/` | Seasonal arrival index (LightGBM quantile forecaster ships in Phase 3) |
| `backend/api/` | FastAPI — exposes recommend, prices, arbitrage, cost estimate, geo, intel |
| `frontend/` | Next.js App Router — mobile-first UI |

---

## API routes

| Endpoint | What |
|---|---|
| `GET /recommend` | Core — ranked mandis + spoilage + cost breakdown |
| `GET /markets/prices` | Live prices by commodity + state |
| `GET /markets/arbitrage` | Same-day spread (high − low) per state |
| `GET /markets/facets` | Available commodities and states |
| `GET /cost/estimate` | Manual what-if: quote → net ₹/tonne |
| `GET /geo/districts` | District lat/lon for a state (GPS fallback picker) |
| `GET /intel/commodity-overview` | National median, peak, top state per commodity |
| `GET /intel/seasonal` | Arrival index by ISO week (lean vs glut signal) |
| `GET /summary` | KPI cards for the home page |

---

## Tech stack

### Why these choices

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Monish's stack; `agmarknet` SDK is Python; first-class pandas/LightGBM |
| Database | Postgres 16 + TimescaleDB | Time-series partitioning on `market_daily`; standard SQL; handles the panel on a laptop |
| Ingestion | `agmarknet` PyPI SDK | Only free source with **arrival volumes** — arrivals predict gluts; data.gov.in has prices only |
| Routing | OSRM self-hosted on Geofabrik India | Free forever, no rate limits, offline; MLD algo for lower RAM than CH |
| Weather | Open-Meteo | Free, no key, hourly along OSRM polyline (Phase 4) |
| Forecasting | LightGBM quantile (P10/P50/P90) | Best tabular time-series; handles categorical `market_id` natively |
| Freshness | Analytical Q₁₀ decay | Physics is well-modeled; a trained model here would be noise-fitting |
| Serving | FastAPI | OpenAPI schema out of the box; pydantic validation |
| Frontend | Next.js (App Router) | SSR, mobile performance, RSC for data-heavy pages |
| Deploy | Docker Compose | Everything in one file; single-host is enough for field validation |

### Deliberately not using

Google Maps, paid weather APIs, ClickHouse, Airflow, Kafka, MLflow, dbt, Kubernetes, cloud PaaS, deep learning. Constraints: 100% free public data, 3-person 12-week build.

### Migrations

Plain numbered SQL files (`backend/db/migrations/NNN_*.sql`), custom runner. No Alembic — schema is small, everything is diffable.

---

## User flows

### Core flow: "Where should I send 5 tonnes of tomatoes?"

1. Land on `/recommend` — commodity, GPS location (or state+district picker), quantity, vehicle, diesel price
2. Tap **Find best mandi** → `GET /recommend`
3. Cards appear ranked by net ₹/tonne — top card is the answer
4. Expand any card → cost waterfall + freshness bar
5. Tap **Directions** → Google Maps with mandi coordinates

### Other pages

| Route | Purpose |
|---|---|
| `/` | Home — KPIs + recent spreads |
| `/recommend` | Core decision screen |
| `/mandis` | Price browser — all mandis for a commodity + state |
| `/estimate` | Manual cost estimator (quote → net ₹/tonne) |
| `/arbitrage` | Spread explorer — commodity × state view |

### Error states

| Situation | Message |
|---|---|
| No mandis in radius | "No mandis reporting [commodity] within [X] km" |
| All destinations spoil | Shows infeasible list with reasons |
| GPS denied | Falls back to state + district picker |
| No cost rates for a state | Mandi shown as infeasible with reason |

---

## Phase timeline

| Phase | Weeks | Status |
|---|---|---|
| 1. Data foundation | 1–2 | Done — Agmarknet ingestion, TimescaleDB schema |
| 2. Cost + freshness reference | 2–4 | Done — AH-66 shelf-life CSV, cost model, OSRM bootstrap |
| 3. Forecasting | 3, 5–7 | Next — LightGBM quantile + backtest harness |
| 4. Freshness engine | 5–6 | After Phase 3 — OSRM + Open-Meteo temperature profile |
| 5. Decision engine + dashboard | 7–9 | ✓ MVP shipped — frontend live |
| 6. Alerts + counterfactual | 9–11 | Pending |
| 7. Field validation + report | 11–12 | Pending |

**Gate:** Phase 6+ only after Phase 5 is solid end-to-end.

---

## Hard constraints (cannot negotiate)

1. **100% free public data** — Agmarknet, data.gov.in, Open-Meteo, OSRM, Nominatim
2. **Freshness is a filter, not a score** — never surface a destination the produce cannot reach alive, even if it would earn more
3. **Scope: 2–3 states, 60–100 mandis** — not all 2000+ mandis, not all of India
4. **Not a price-display app** — the differentiator is the decision (which mandi, netted for cost and decay)
