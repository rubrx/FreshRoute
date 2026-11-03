# CLAUDE.md — FreshRoute

Project context for future Claude sessions. Read this first.

## What this project is

**FreshRoute** — spoilage-aware mandi routing for Indian agricultural traders, FPOs, and aggregators.

> Rank candidate mandis by expected net ₹/tonne after spoilage, freight, and commission — with a hard feasibility filter that rejects any destination the produce cannot survive.

Full architecture and tech decisions in [`docs/architecture.md`](./docs/architecture.md).

## Team & constraints

- **Rubrangso** (full-stack + infra), **Monish** (AI/ML), **Tanishq** (management/ops)
- 12 weeks · 100% free public data only · B.Tech IT capstone — IIIT Una 2023–27

## Key insight

Same-day spread between mandis (40–100%) dwarfs realistic 1–7 day forecast error (~15%). Value comes from **arbitrage visibility + cost-netting + spoilage feasibility**. Forecasting is the tiebreaker on *when*, not the core claim.

## Hard gates

| Gate | When | Test |
|---|---|---|
| **Gate 1 — panel density** | End of week 2 | ≥ 60% of expected reporting days covered |
| **Gate 2 — cost model** | End of week 4 | `backend/cost/model.py` returns itemized ₹/tonne with sourced state rates |
| **Gate 3 — core done** | End of week 9 | Ingestion → ranker → dashboard all working end-to-end |

Stretch features S1–S5 only after Gate 3.

## Phase status

| Phase | Weeks | Status | Owner |
|---|---|---|---|
| 1. Data foundation | 1–2 | Done | R |
| 2. Cost + freshness reference | 2–4 | Done | T + M + R |
| 3. Forecasting | 3, 5–7 | Next | M |
| 4. Freshness engine | 5–6 | Pending | R |
| 5. Decision engine + dashboard | 7–9 | MVP shipped | R + M |
| 6. Alerts + counterfactual | 9–11 | Pending | R + M |
| 7. Field validation + report | 11–12 | Pending | T + all |

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Postgres 16 + TimescaleDB, SQLAlchemy 2.0
- **Ingestion:** `agmarknet` PyPI SDK + data.gov.in REST; pandas/pyarrow; plain SQL migrations
- **Routing:** OSRM self-hosted (MLD) on Geofabrik India extract
- **Weather:** Open-Meteo (Phase 4, hourly along route)
- **ML:** LightGBM quantile P10/P50/P90 + rolling-origin backtest (Phase 3)
- **Freshness:** analytical Q₁₀ decay integrator — no ML
- **Frontend:** Next.js (App Router), TypeScript, Tailwind
- **Deploy:** Docker Compose

## Docs

| File | What |
|---|---|
| `docs/architecture.md` | System design, data flow, API routes, tech decisions, phase timeline |
| `docs/shelf-life.md` | AH-66 transcription rules, Q₁₀ assignments, Indian-context caveats |
| `docs/data-reference.md` | Reference CSVs — schema, sources, how to update |

## Ground rules

1. **Not a price-display app.** The differentiator is the decision (which mandi, netted for cost and decay). Every UI surface must justify itself against that.
2. **Freshness is a hard filter.** Never show a destination the produce cannot reach alive, even if it would earn more.
3. **Agmarknet is primary** — it has arrival volumes. `data.gov.in` is prices-only, used only as the live daily feed.
4. **Never commit secrets.** `.env.example` is the template.
5. **Dates: DD/MM/YYYY on ingest → ISO everywhere else.**
6. **Markets report sparsely.** Never assume today's record exists.
7. **Scope:** 2–3 states, 60–100 mandis. Not all of India.

## Not in scope

Paid APIs (Google Maps, commercial weather), ClickHouse, Airflow, Kafka, Kubernetes, cloud PaaS, deep learning, computer vision, live GPS tracking, all 2000+ mandis, stretch features S1–S5 before week 9.
