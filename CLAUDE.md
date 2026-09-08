# CLAUDE.md — FreshRoute

Project context for future Claude sessions. Read this first.

## What this project is

**FreshRoute** — a spoilage-aware mandi routing and price intelligence engine for Indian agricultural traders, FPOs, and aggregators.

The full product spec is in [`buildplan.md`](./buildplan.md), the capstone proposal is in [`docs/proposal.md`](./docs/proposal.md), and the deliberate tech-stack rationale is in [`docs/tech-stack.md`](./docs/tech-stack.md). Read the proposal before making architectural decisions. The one-line pitch:

> Rank candidate mandis by expected net ₹/tonne after spoilage, freight, and commission — with a hard feasibility filter that rejects any destination the produce cannot survive.

## Team & constraints

- **3 people:** Rubrangso (full-stack + infra), Monish (AI/ML), Tanishq (management/ops)
- **12 weeks** total
- **100% free public data** only (Agmarknet, data.gov.in, USDA AH-66, Open-Meteo, OSM/OSRM)
- **B.Tech IT capstone** — IIIT Una, 2023–27

## Origin & key insight

Selected from a 28-idea shortlist scored across nine criteria. The two hard constraints (100% free public data + 3-month build with a 3-person team) killed the initial front-runner (a COD/RTO risk engine, blocked on labeled Indian delivery data), then killed diesel-shrinkage, facility-dwell, near-expiry pharma, handwritten-bilty OCR, warehouse-slotting, and — critically — the incumbent choice of visual defect inspection (plays to Monish's weakest area; MVTec-AD reads as coursework).

Mandi routing survived because **Agmarknet publishes ~18 years of daily price and arrival-volume data for free**, and because of one framing insight:

> Same-day spread between mandis (40–100%) dwarfs realistic 1–7 day forecast error (~15%). So value comes from **arbitrage visibility + cost-netting + spoilage feasibility**. Forecasting is the tiebreaker on *when*, not the core claim.

Every design decision serves that framing. See [`docs/proposal.md`](./docs/proposal.md) §3 for the full "why this project, why not the other 27."

## Hard gates

Three gates are binding. Missing any of them means the project stalls; the code is written to make them non-negotiable.

| Gate | When | Test | Failure mode |
|---|---|---|---|
| **Gate 1 — panel density** | End of week 2 | Do enough mandis report ≥ 60% of expected days? | If no, expand states or re-scope commodities *before* modeling. |
| **Gate 2 — cost model exists** | End of week 4 | Does `backend/cost/model.py` return itemized ₹/tonne with sourced state rates? | The optimizer cannot be written without an objective function. Tanishq's hard deadline. |
| **Gate 3 — core done** | End of week 9 | Ingestion → forecasts → freshness → ranker → dashboard all working? | Only touch stretch features S1–S5 if this passes. |

## Working files

| File | Purpose |
|---|---|
| `buildplan.md` | Full product + technical plan. Original scoping doc. |
| `docs/proposal.md` | Capstone proposal — origin, differentiators, timeline, defense line. |
| `docs/tech-stack.md` | Every tech choice with rationale + what was rejected. |
| `docs/shelf-life-notes.md` | AH-66 transcription rules, Q₁₀ assignment logic, Indian-context caveats. |
| `CLAUDE.md` | This file. Orientation for Claude sessions. |
| `PROGRESS.md` | What's shipped. Append-only log of completed work per phase. |
| `TODO.md` | What's next. Full phase-by-phase backlog. Update as work moves. |

## Phase structure

Work is organized into 7 phases mapped to the 12-week timeline in `buildplan.md §8`:

| Phase | Weeks | Focus | Owner |
|---|---|---|---|
| **1. Data foundation** | 1–2 | Ingestion pipeline, TimescaleDB schema, data quality gate | R |
| **2. Cost + freshness reference data** | 2–4 | AH-66 shelf-life CSV, cost model v1, seasonal arrival index, OSRM + geocoding | T + M + R |
| **3. Forecasting** | 3, 5–7 | Backtest harness, LightGBM quantile price forecaster, arrival forecaster | M |
| **4. Freshness engine service** | 5–6 | OSRM route → Open-Meteo profile → Q₁₀ decay → remaining life `R` | R |
| **5. Decision engine + dashboard** | 7–9 | Feasibility filter + net realization ranker, mobile dashboard | R + M |
| **6. Alerts + counterfactual ledger** | 9–11 | WhatsApp/SMS, abstention logic, ₹/tonne uplift backtest | R + M |
| **7. Field validation + report** | 11–12 | Trader interviews, thesis, defense deck | T + all |

**Week 2 gate:** panel dense enough? Week 9 gate: core done before touching stretch features S1–S5.

## Tech stack (summary — full rationale in `docs/tech-stack.md`)

- **Language:** Python 3.11+
- **Data pipeline:** pandas · pyarrow · `agmarknet` PyPI · httpx + tenacity · structlog
- **Database:** Postgres 16 + TimescaleDB hypertable (1-month chunks). SQLAlchemy 2.0 sync + psycopg2. Plain SQL migrations (numbered, custom runner)
- **Config + CLI:** pydantic-settings · python-dotenv · Typer
- **Routing:** OSRM self-hosted (MLD algorithm) on Geofabrik India extract
- **Geocoding:** Nominatim public server, polite rate limits (fallback: self-host)
- **Weather:** Open-Meteo (no key, hourly along OSRM polyline)
- **Forecasting:** LightGBM quantile objective (P10/P50/P90) · rolling-origin backtest · conformal prediction for abstention
- **Freshness engine:** analytical Q₁₀ decay integrator (no ML)
- **Serving:** FastAPI + nightly batch scoring → Postgres
- **Dashboard:** mobile-first; Next.js vs React+Vite decided at Phase 5
- **Alerts:** Twilio / Gupshup sandbox — WhatsApp + SMS, Hindi + English
- **Deploy:** Docker Compose
- **Testing + lint:** pytest · pytest-cov · ruff

**Deliberately not using:** Google Maps, paid weather APIs, ClickHouse, Airflow, Kafka, MLflow, dbt, Kubernetes, cloud PaaS, deep learning, computer vision. Rationale for each rejection in `docs/tech-stack.md`.

## Repo layout

```
practicum/
├── buildplan.md              # Full plan — source of truth
├── CLAUDE.md                 # This file
├── PROGRESS.md               # Completed work log
├── TODO.md                   # Phase backlog
├── docker-compose.yml        # Postgres/TimescaleDB, OSRM (added later)
├── .env.example              # Secret template — never commit real .env
├── backend/
│   ├── pyproject.toml
│   ├── config/               # Settings + env loading
│   ├── db/
│   │   ├── migrations/       # Plain SQL, numbered
│   │   └── connection.py
│   ├── ingestion/            # Agmarknet client, normalize, quality, backfill, daily
│   ├── forecasting/          # (Phase 3) LightGBM + backtest harness
│   ├── freshness/            # (Phase 4) Q₁₀ decay + route service
│   ├── cost/                 # (Phase 2) Freight, commission, cess, labour
│   ├── decision/             # (Phase 5) Ranker + feasibility filter
│   └── api/                  # (Phase 5) FastAPI recommendation service
├── data/
│   ├── raw/                  # Agmarknet dumps, never edited
│   ├── processed/            # Cleaned panel snapshots
│   └── reference/            # AH-66 shelf-life CSV, mandi geocodes, cost tables
├── docs/                     # Data quality reports, phase writeups
└── scripts/                  # One-off ops scripts
```

## Ground rules

1. **Follow the plan.** Do not add features outside the current phase. Scope creep is the #1 killer of this project (see `buildplan.md §3`).
2. **Update `PROGRESS.md` and `TODO.md`** whenever something ships or the plan changes.
3. **Never commit secrets.** All API keys go in `.env`. `.env.example` is the template.
4. **Agmarknet is the primary data source** — via the `agmarknet` PyPI package. It carries *both* prices and arrival volumes. `data.gov.in` is **prices-only** (no arrivals) and is used only as a live daily feed, never as a history source. Arrivals matter because arrivals predict the glut.
5. **Dates: DD/MM/YYYY on ingest → ISO everywhere else.**
6. **Markets report sparsely.** Never assume today's record exists. Always show the most recent.
7. **Frame forecasting honestly:** value comes from arbitrage visibility + cost netting + spoilage feasibility. Forecasting is the tiebreaker on *when*, not the core claim.
8. **This is not a price-display app.** Agmarknet dashboards already exist on GitHub. The differentiator is the **decision** (which mandi, netted for cost and decay), not the display. Every UI surface must justify itself against that standard.
9. **Freshness is a hard constraint, not a footnote.** Destinations are filtered *before* being ranked by price. Never show a destination the produce cannot reach alive, even if it would be the highest earner.
10. **Do not hard-code a crop calendar.** The seasonal index is derived from ~18 years of Agmarknet arrivals per (commodity, state, ISO week). NHB Horticultural Statistics is a sanity cross-check only (MoSPI has flagged its subjective ground-level reporting divergence from DESMOA).
11. **The defense line:** *"Over 90 days of historical backtesting across N mandis, our recommendations would have earned ₹X more per tonne than the default policy, while keeping Y% of consignments within shelf life vs Z% for the baseline."* Every design decision should serve that sentence.

## Not in scope (say no)

- All 2000+ mandis. Scope is 2–3 states, 60–100 mandis.
- A price-display app / Agmarknet dashboard clone.
- Computer vision, satellite imagery, IoT sensors.
- Live GPS truck tracking.
- Paid data sources (Google Maps distance matrix, commercial weather APIs, GoKwik-style paid feeds).
- Deep learning, CNNs, transformers for forecasting. LightGBM only.
- Airflow / Kafka / Kubernetes / cloud PaaS.
- Stretch features S1–S5 before week 9.

## Current state

Phase 1 and Phase 2 scaffolding shipped. See `PROGRESS.md` for exactly what's landed and `TODO.md` for what's next. Phase 3 (forecasting) starts once Phase 1 backfill runs against real data.
