# FreshRoute

> Rank candidate mandis by expected net ₹/tonne after spoilage, freight, and commission — with a hard feasibility filter that rejects any destination the produce cannot survive.

Capstone project — IIIT Una, 2023–27. 100% free public data. No paid APIs.

---

## Quick start (5 commands)

```bash
# 1. Database
cp .env.example .env
docker compose up -d db

# 2. Backend
cd backend && pip install -e . && cd ..
python -m backend.cli migrate

# 3. Seed data (small test run — ~5 min)
python -m backend.cli backfill \
    --states Maharashtra \
    --commodities Tomato \
    --start 2024-01-01

# 4. API server
uvicorn backend.api.main:app --reload
# → http://127.0.0.1:8000/docs

# 5. Frontend
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

Full historical backfill (2007–present, 3 states × 4 commodities) takes several hours and is resumable.

---

## Architecture

```
 data.gov.in  ──────────┐
 Agmarknet SDK ─────────┤──► Ingestion ──► Postgres + TimescaleDB
                        │        │              │
             AH-66 CSV ─┘   costs.csv ─────────┤
        district CSVs ──────────────────────────┤
                                                │
                OSRM (self-hosted) ─────────────┼──► FastAPI ──► Next.js
              Open-Meteo (free) ────────────────┘    :8000      :3000
```

The decision engine fetches price + route + weather at query time and returns a ranked list of feasible mandis — no precomputed scores.

---

## API surface

| Method | Path | Returns |
|--------|------|---------|
| GET | `/summary` | KPI cards for the home dashboard |
| GET | `/markets/facets` | Distinct commodities + states |
| GET | `/markets/arbitrage` | Ranked intra-state price spreads |
| GET | `/markets/prices` | Per-mandi prices for one commodity |
| GET | `/cost/estimate` | Itemized ₹ breakdown for a consignment |
| GET | `/recommend` | Best mandis ranked by net ₹/tonne |
| GET | `/intel/commodity-overview` | Multi-commodity widget data |
| GET | `/intel/seasonal` | 52-week arrival-index sparkline |
| GET | `/geo/districts` | District lat/lon for GPS-fallback picker |

Full docs at `http://localhost:8000/docs` after starting the API.

---

## Data sources

| Source | What | Access |
|--------|------|--------|
| [Agmarknet](https://agmarknet.gov.in) | 18 yr daily prices + arrivals | `agmarknet` PyPI SDK |
| [data.gov.in](https://data.gov.in) | Live daily price feed | HTTP REST (prices only, no arrivals) |
| USDA AH-66 | Shelf-life tables per commodity | Transcribed to `data/reference/shelf_life.csv` |
| OSRM (self-hosted) | Road distances + travel times | Docker, Geofabrik India extract |
| Open-Meteo | Temperature profile along route | Free API, no key required |
| `data/reference/costs.csv` | APMC commission + cess rates by state | Manually sourced from state APMC rules |

---

## Repo layout

```
practicum/
├── backend/
│   ├── api/            FastAPI app + routers
│   ├── analysis/       Market intelligence (price stats, seasonal index)
│   ├── cost/           Freight + APMC cost model
│   ├── decision/       Spoilage-aware mandi ranker
│   ├── ingestion/      Agmarknet client, normalize, upsert, backfill
│   └── db/             Migrations + SQLAlchemy engine
├── frontend/           Next.js 15 App Router dashboard
├── data/
│   ├── raw/            Agmarknet dumps (gitignored)
│   ├── processed/      Cleaned snapshots + seasonal index (gitignored)
│   └── reference/      Versioned CSV tables (shelf life, costs, geocodes)
└── docs/               Proposal, tech-stack rationale, quality reports
```

---

## Team

| Person | Role |
|--------|------|
| Rubrangso | Full-stack + infra (ingestion, freshness, API, dashboard) |
| Monish | AI/ML (backtest harness, LightGBM forecasters, seasonal index) |
| Tanishq | Management/ops (cost model, field interviews, business case) |

See [`PROGRESS.md`](./PROGRESS.md) for what's shipped and [`TODO.md`](./TODO.md) for what's next.
