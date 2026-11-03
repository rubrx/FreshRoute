# FreshRoute

Spoilage-aware mandi routing for Indian agricultural traders. Ranks candidate mandis by expected net ₹/tonne after spoilage loss, freight, and market charges — rejecting any destination the produce cannot survive.

## What it does

- **Recommends mandis** — filters out destinations your produce can't reach while still sellable, then ranks survivors by net ₹/tonne
- **Shows same-day spreads** — the price gap between cheapest and priciest mandi per state
- **Price intelligence** — live Agmarknet modal prices, searchable by commodity and state
- **Cost calculator** — itemised deduction breakdown: freight, APMC commission, cess, entry fee, labour, weighment

## Quick start

```bash
# 1. Start Postgres + TimescaleDB
docker compose up -d db

# 2. Backend (Python 3.11+)
cd backend
pip install -e ".[dev]"
uvicorn backend.api.main:app --reload   # http://localhost:8000

# 3. Frontend (Node 20+, pnpm)
cd frontend
pnpm install
pnpm dev                                # http://localhost:3000
```

Copy `.env.example` → `.env` at the repo root before starting.

## Project layout

```
practicum/
├── backend/
│   ├── api/          FastAPI routes + schemas
│   ├── ingestion/    Agmarknet → TimescaleDB pipeline
│   ├── decision/     Net ₹/tonne ranker + feasibility filter
│   ├── cost/         Freight, commission, cess, labour model
│   ├── analysis/     Price intelligence (percentile rank, vs-median)
│   └── freshness/    OSRM distance matrix (Q₁₀ engine in Phase 4)
├── frontend/src/
│   ├── app/          Next.js App Router pages
│   ├── components/   UI — features/, layout/, ui/
│   ├── lib/          API client + formatters
│   └── styles/       Design tokens
├── data/reference/   AH-66 shelf-life CSV, mandi geocodes, cost tables
└── docs/             Architecture, shelf-life notes, data reference
```

## Data sources

| Source | What | How |
|---|---|---|
| [Agmarknet](https://agmarknet.gov.in) | 18yr daily prices + arrival volumes | `agmarknet` PyPI SDK |
| [data.gov.in](https://data.gov.in) | Live daily price feed (prices only) | REST API, free key |
| [Open-Meteo](https://open-meteo.com) | Hourly temperature along route (Phase 4) | Free REST, no key |
| [OSRM](http://project-osrm.org) | Road distance + duration | Self-hosted, Geofabrik India extract |
| USDA AH-66 | Shelf-life Q₁₀ parameters | Transcribed to `data/reference/shelf_life.csv` |

## Docs

- [`docs/architecture.md`](docs/architecture.md) — system design, API routes, tech decisions, phase timeline
- [`docs/shelf-life.md`](docs/shelf-life.md) — AH-66 transcription rules, Q₁₀ assignments, Indian-context caveats
- [`docs/data-reference.md`](docs/data-reference.md) — reference CSVs: schema, sources, how to update

## B.Tech IT Capstone — IIIT Una 2023–27

Team: Rubrangso (full-stack + infra), Monish (AI/ML), Tanishq (management/ops).
