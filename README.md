# FreshRoute

Spoilage-aware mandi routing and price intelligence for Indian agri traders. Capstone project — IIIT Una, 2023–27.

**Start here:**

| Doc | Purpose |
|---|---|
| [`docs/proposal.md`](./docs/proposal.md) | The capstone proposal — problem, origin, differentiators, timeline, defense line |
| [`docs/tech-stack.md`](./docs/tech-stack.md) | Every technology choice with rationale + what was rejected |
| [`buildplan.md`](./buildplan.md) | Original scoping doc; retained for continuity |
| [`CLAUDE.md`](./CLAUDE.md) | Session orientation for Claude — hard gates + ground rules |
| [`PROGRESS.md`](./PROGRESS.md) | What's shipped, phase by phase |
| [`TODO.md`](./TODO.md) | What's next, phase by phase |

## What's shipped

Phase 1 (data foundation) and Phase 2 (cost + freshness reference data + OSRM + geocoding scaffolding) — see [`PROGRESS.md`](./PROGRESS.md).


## What's next

Phase 3 (forecasting) — see [`TODO.md`](./TODO.md). Blocked on running the actual historical backfill and passing **Gate 1** (panel density ≥ 60% per mandi).

---

## Quickstart

Prereqs: Docker, Python 3.11+, and `pip`.

### 1. Start the database

```bash
cp .env.example .env      # tweak if you already run Postgres on 5433
docker compose up -d db
```

Confirm it's up:

```bash
docker compose ps
docker compose exec db pg_isready -U freshroute
```

### 2. Install the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Apply migrations

```bash
python -m backend.cli migrate
```

You should see `Applied 4 migration(s): ['001', '002', '003', '004']`. Re-running is a no-op.

### 4. Backfill data

Start small to verify the SDK works:

```bash
python -m backend.cli backfill \
    --states Maharashtra \
    --commodities Tomato \
    --start 2024-01-01
```

Then run the full matrix for Phase 1. State choice depends on reporting density — the plan targets 2–3 states, 60–100 mandis:

```bash
python -m backend.cli backfill \
    --states "Maharashtra,Karnataka,Uttar Pradesh" \
    --commodities "Tomato,Onion,Potato,Banana" \
    --start 2007-01-01
```

The backfill is chunked by year and resumable — kill it any time; re-running picks up where it stopped (progress cursor in `data/raw/agmarknet/state.json`).

### 5. Data quality report

```bash
python -m backend.cli quality --min-density 0.6
```

Writes `docs/data-quality-report.md`. Use it to decide which mandis clear the week-2 gate.

### 6. Daily incremental pull (later)

Hook this up to cron / a scheduled job:

```bash
python -m backend.cli daily \
    --states "Maharashtra,Karnataka" \
    --commodities "Tomato,Onion,Potato,Banana" \
    --lookback-days 7
```

---

## Repo layout

```
practicum/
├── buildplan.md              # Full plan — source of truth for scope
├── CLAUDE.md                 # Session orientation for Claude
├── PROGRESS.md               # Append-only log of shipped work
├── TODO.md                   # Phase-by-phase backlog
├── docker-compose.yml        # Postgres + TimescaleDB (OSRM added in Phase 2)
├── .env.example              # Secret template
├── backend/
│   ├── pyproject.toml
│   ├── config/               # pydantic-settings env loader
│   ├── db/
│   │   ├── connection.py     # SQLAlchemy engine + session scope
│   │   ├── migrate.py        # Plain-SQL migration runner
│   │   └── migrations/       # 001…004
│   ├── ingestion/
│   │   ├── agmarknet_client.py   # Retrying wrapper around the SDK
│   │   ├── normalize.py          # Column aliasing, date parsing, dedupe
│   │   ├── upsert.py             # Auto-registering upsert into panel
│   │   ├── backfill.py           # Year-chunked, resumable historical pull
│   │   ├── daily.py              # Incremental N-day pull
│   │   └── quality.py            # Reporting-density + anomaly report
│   └── cli.py                # typer CLI: migrate | backfill | daily | quality
├── data/
│   ├── raw/                  # Agmarknet dumps (gitignored)
│   ├── processed/            # Cleaned snapshots (gitignored)
│   └── reference/            # Versioned reference tables (shelf life, costs, geocodes)
├── docs/                     # Quality reports, phase writeups
└── scripts/                  # Ops one-offs
```

---

## Team

- **Rubrangso** — full-stack + infra (ingestion, freshness engine, API, dashboard, deploy)
- **Monish** — AI/ML (backtest harness, LightGBM forecasters, seasonal index, abstention)
- **Tanishq** — management/ops (cost model, field interviews, business case)

Owner map and per-phase deliverables are in `TODO.md`.
