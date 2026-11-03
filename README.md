# FreshRoute

Spoilage-aware mandi routing for Indian agricultural traders. Ranks candidate mandis by expected net ₹/tonne after spoilage loss, freight, and market charges — rejecting any destination the produce cannot survive.

## What it does

- **Recommends mandis** — filters out destinations your produce can't reach while still sellable, then ranks survivors by net ₹/tonne
- **Shows same-day spreads** — the price gap between the cheapest and priciest mandi in each state, net of indicative freight
- **Price intelligence** — live Agmarknet modal prices across all reporting mandis, searchable by commodity and state
- **Cost calculator** — itemised deduction breakdown: freight, APMC commission, cess, entry fee, labour, weighment

## Quick start

```bash
# 1. Backend (Python 3.11+)
cd backend
cp ../.env.example ../.env        # fill POSTGRES_URL
pip install -e ".[dev]"
uvicorn api.main:app --reload

# 2. Frontend (Node 20+)
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

Requires Postgres 16 + TimescaleDB. See `docker-compose.yml` for a one-command local setup.

## Project tree

```
practicum/
├── backend/
│   ├── api/          FastAPI routes + schemas
│   ├── ingestion/    Agmarknet → TimescaleDB pipeline
│   ├── decision/     Net ₹/tonne ranker + feasibility filter
│   ├── cost/         Freight, commission, cess, labour model
│   └── freshness/    Q₁₀ decay integrator (route × weather)
├── frontend/
│   └── src/
│       ├── app/      Next.js App Router pages
│       ├── components/
│       │   ├── features/  MandiCard, SpreadBar, RecommendCard …
│       │   ├── layout/    Navbar, Footer
│       │   └── ui/        Panel, KpiCard, LoadingCard
│       ├── lib/      API client + formatters
│       └── styles/   Design tokens (CSS custom properties)
├── data/
│   ├── raw/          Agmarknet dumps — never edited
│   └── reference/    AH-66 shelf-life CSV, mandi geocodes, cost tables
└── docs/             Proposal, tech-stack rationale, shelf-life notes
```

## Key decisions

| Decision | Rationale |
|---|---|
| **Agmarknet as primary source** | 18 years of daily price + arrival volume, free via the `agmarknet` PyPI package. Arrivals predict gluts; data.gov.in has prices only. |
| **Freshness as a hard filter, not a score** | Never surface a destination the produce can't reach alive — even if it would earn more. Q₁₀ decay + OSRM route + Open-Meteo temperature profile. |
| **LightGBM quantile forecasting** | P10/P50/P90 bounds calibrated against 3-day rolling-origin backtests. Value is arbitrage visibility, not forecast precision. |
| **No paid APIs** | 100% free public data — Google Maps, commercial weather, and GoKwik-style feeds are explicitly out of scope. |

## Data sources

| Source | What we use | How |
|---|---|---|
| [Agmarknet](https://agmarknet.gov.in) | Historical daily prices + arrival volumes | `agmarknet` PyPI package |
| [data.gov.in](https://data.gov.in) | Live daily price feed (prices only, no arrivals) | REST API with free key |
| [Open-Meteo](https://open-meteo.com) | Hourly temperature along route | Free REST, no key |
| [OSRM](http://project-osrm.org) | Road distance + duration | Self-hosted on Geofabrik India extract |
| USDA AH-66 | Shelf-life parameters (Q₁₀, base life) | Transcribed to `data/reference/shelf_life.csv` |

## B.Tech IT Capstone — IIIT Una 2023–27

Team: Rubrangso (full-stack + infra), Monish (AI/ML), Tanishq (management/ops).
Full proposal and timeline in [`docs/proposal.md`](docs/proposal.md).
