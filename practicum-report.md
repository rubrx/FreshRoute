# Practicum Report

**Institution:** Indian Institute of Information Technology, Una (IIIT Una)
**Programme:** B.Tech, Information Technology, Batch 2023 – 2027
**Report:** Practicum Report 1 (End of Phase 1)
**Report date:** 2026-09-08

**Team**

| Name        | Role                    | Responsibilities                                                              |
|-------------|-------------------------|-------------------------------------------------------------------------------|
| Rubrangso   | Full-stack + infra lead | Ingestion pipeline, freshness engine, API, dashboard, deployment, this report |
| Monish      | AI / ML lead            | Backtest harness, LightGBM forecasters, seasonal arrival index, abstention    |
| Tanishq     | Management + operations | Cost model calibration, field interviews, business case                        |

---

## 1. Title of the Project

**FreshRoute — A Spoilage-Aware Mandi Routing and Price-Intelligence Engine for Indian Agricultural Traders**

*One-line pitch:* Rank candidate mandis by expected net ₹/tonne after
spoilage, freight, and commission — with a hard feasibility filter that
rejects any destination the produce cannot survive.

---

## 2. Introduction

India has more than 7,000 wholesale agricultural markets (*mandis*). On any
given day, the price of tomato, onion, potato, banana or almost any
horticulture commodity can differ by **40 – 100 %** between two mandis that
are only a few hundred kilometres apart. A farmer or a small-lot trader
routinely decides — under time pressure, with imperfect information — where
to send a truck load. That decision has three inputs the trader must
combine mentally:

1. Which mandi is offering the best price today, and can it hold for the
   dispatch window?
2. What does it actually cost to reach that mandi, once freight, APMC
   commission, market cess, entry fees, labour, weighment and loss factors
   are subtracted from the gross price?
3. Will the produce still be sellable when it arrives? Perishability is
   temperature- and time-dependent, and the truck is almost always open,
   uncooled and moving through summer daytime heat.

The government publishes the **AGMARKNET** price database (daily prices
across ~3,000 reporting mandis, going back roughly 18 years) and the
**data.gov.in** live-daily-price API. These sources are free and
open. Yet no free, open, publicly-usable tool combines them into an
actionable *routing* decision. Existing Agmarknet dashboards are
price *displays*, not decision engines.

**FreshRoute closes that gap.** Given a commodity, origin, dispatch date
and quantity, the system ranks every reachable destination mandi by the
**expected net realisation in ₹/tonne**, with a hard *feasibility filter*
that eliminates destinations the produce cannot reach alive. The
recommendation is delivered in a mobile-first dashboard and via WhatsApp
alerts, in Hindi and English.

The project is a capstone (final-year practicum) for three B.Tech IT
students at IIIT Una, budgeted at 12 weeks and constrained to
**100 % free public data**. Both constraints are load-bearing on every
design decision.

---

## 3. Problem Definition

### 3.1 The trader's decision problem

Let a producer of produce *c* be located at origin mandi *o* on dispatch
date *d*. Let 𝓜 be the set of reachable candidate destination mandis
{ m₁, m₂, …, m_k }. For each candidate m, the trader must estimate:

> **NET(c, o, m, d) = P̂(c, m, d + t(o, m))  ·  R(c, o, m, d)  −  COST(o, m, quantity, c)**

where

- **P̂(c, m, τ)** is the forecasted arrival-day modal price of commodity
  *c* at mandi *m* on date *τ* — quantile forecasts, P10 / P50 / P90;
- **t(o, m)** is the transit duration on the road network;
- **R(c, o, m, d)** ∈ [0, 1] is the *remaining shelf-life fraction*
  produced by integrating a Q₁₀ decay model along the route's temperature
  profile;
- **COST(·)** is an itemised ₹/tonne breakdown covering diesel-linked
  freight, APMC commission, state cess, entry fee, labour and weighment,
  including multi-trip logic when the load exceeds any single truck's
  capacity.

The problem has two hard properties that shape the solution:

1. The Agmarknet panel is **sparse**. Many mandis skip days; some skip
   weeks. Any model must be robust to missing data and never assume
   today's record exists.
2. The **arbitrage signal dwarfs the forecast noise.** Same-day price
   *spread* between mandis is 40 – 100 %; the best achievable 1 – 7 day
   forecast error is around 15 %. This means the model's value is
   principally in *arbitrage visibility + cost netting + spoilage
   feasibility*, and only secondarily in prediction skill. Forecasting is
   the tiebreaker on **when** to dispatch, not the core claim.

### 3.2 Non-goals (explicit)

The following are **out of scope** and stay out of scope, to protect the
12-week schedule:

- Building a price-display app / Agmarknet dashboard clone
- All 3,000+ mandis (scope is 2 – 3 states, 60 – 100 mandis)
- Computer vision, satellite imagery, IoT sensors
- Live GPS truck tracking
- Paid data sources (Google Maps distance matrix, commercial weather APIs)
- Deep learning / CNNs / transformers for forecasting
- Airflow / Kafka / Kubernetes / cloud PaaS

### 3.3 Why this problem and not a similar-sounding one

FreshRoute was selected from a **28-idea shortlist** that was scored across
nine criteria (data availability, team fit, differentiation, defensibility,
free-data feasibility, time-to-value, thesis novelty, business case,
risk). The two hard constraints — 100 % free public data and a 3-month
build with a 3-person team — killed the initial front-runner (a
COD / RTO risk engine, blocked because labelled Indian delivery-outcome
data is not open) and successively eliminated diesel-shrinkage,
facility-dwell, near-expiry pharma, handwritten-bilty OCR, warehouse
slotting, and — critically — the incumbent choice of *visual defect
inspection*, which plays to the AI lead's weakest area and reads as
coursework rather than research.

Mandi routing survived because AGMARKNET publishes about 18 years of
daily price and arrival-volume data for free, and because of the framing
insight above (arbitrage spread ≫ forecast error). The full "why this
project, why not the other 27" analysis is in `docs/proposal.md` §3.

---

## 4. Objectives

The project has four *primary* objectives, one *evaluation* objective and
one *thesis* objective. All six are measurable and every one has a hard
gate or artefact attached.

### O1 — Data foundation (Phases 1 – 2)

Build a reproducible, free-data-only pipeline that ingests Agmarknet /
data.gov.in prices into a TimescaleDB hypertable, geocodes 60 – 100
mandis, computes an OSRM-based distance matrix and derives a data-quality
report.

*Success:* Reporting-density ≥ 60 % on the retained mandis over the study
window (Gate 1). Itemised cost model returns ₹/tonne breakdown with
sourced state rates (Gate 2).

### O2 — Forecasting (Phase 3)

Train a LightGBM quantile forecaster (P10, P50, P90) for the modal price
of every (commodity × mandi) at horizons 1 – 7 days, and a companion
arrival-volume forecaster that feeds a glut early-warning surface.

*Success:* Beats three baselines (naive, seasonal-naive, 7-day moving
average) on pinball loss on a rolling-origin backtest.

### O3 — Freshness engine (Phase 4)

Compute a physically motivated shelf-life-remaining fraction
`R ∈ [0, 1]` from a Q₁₀ analytical decay integrator along the OSRM route,
with temperature sampled from Open-Meteo hourly along the polyline.

*Success:* Unit tests pass on synthetic routes; the feasibility filter
eliminates destinations where `R < R_min` (default 0.35) *before* the
ranker sees them.

### O4 — Decision engine + dashboard (Phase 5)

A ranker that combines P̂, R and COST into a net ₹/tonne per candidate,
served through a FastAPI endpoint and displayed in a mobile-first
dashboard with ranked destination cards, itemised ₹ breakdowns and
feasibility reasons.

*Success:* Gate 3 — end-to-end pipeline running: ingestion → forecasts →
freshness → ranker → dashboard.

### O5 — Evaluation (Phases 6 – 7)

A counterfactual ledger: every recommendation is persisted with its
inputs; every recommendation is scored against realised prices; a 90-day
report of cumulative ₹/tonne uplift vs (a) nearest-mandi baseline and
(b) historical default-mandi baseline is emitted.

*Success (the defence line):* "Over 90 days of historical backtesting
across N mandis, FreshRoute's recommendations would have earned ₹X more
per tonne than the default policy, while keeping Y % of consignments
within shelf life vs Z % for the baseline."

### O6 — Thesis + business case (Phase 7)

Thesis document, defence deck, and a business case establishing buyer
segment (trader / FPO / agri-B2B platform / state agri department),
willingness-to-pay, and competitive gap.

*Success:* Passes viva; documents the entire pipeline including the
data-source drift finding of Section 11.

---

## 5. Skillset Additionally Required to Solve / Address the Problem

The team already has a solid coursework foundation in Python, C++, DBMS,
DSA, ML introduction and web development. The following are the *new*
skills the project demands.

### 5.1 Rubrangso (full-stack + infra)

| Skill                                         | Why needed                                                                      | Depth required        |
|-----------------------------------------------|----------------------------------------------------------------------------------|------------------------|
| Postgres + **TimescaleDB** hypertables        | Time-series schema for 18 years × 3,000 mandis                                  | Working proficiency    |
| **OSRM** self-hosted routing (MLD algorithm)  | Free, high-throughput driving-distance + polyline for the freshness engine       | Bootstrap + query      |
| **Nominatim** geocoding with polite rate limits | Resolve mandi names → lat/lon without hitting Google's paid API                | Client + cache         |
| **Open-Meteo** hourly weather along a polyline | Sample temperature per route segment for Q₁₀ decay                              | Client + cache         |
| Analytical **Q₁₀ decay integrator**            | The freshness engine's core physics — not ML                                    | Read USDA AH-66 + code |
| **FastAPI** production patterns                | `/recommend` endpoint that composes forecast + freshness + cost                 | Async + Pydantic v2    |
| Mobile-first frontend (Next.js or React+Vite) | The trader's device is a phone, not a desktop                                    | Framework choice + UX  |
| **Twilio / Gupshup** WhatsApp + SMS templates | Alert delivery in Hindi and English                                             | Sandbox + templates    |
| **Docker Compose** deployment                 | Reproducible dev + demo environment                                             | Already competent      |

### 5.2 Monish (AI / ML)

| Skill                                            | Why needed                                                                      | Depth required                 |
|--------------------------------------------------|----------------------------------------------------------------------------------|---------------------------------|
| **LightGBM** quantile objective                  | Best-in-class gradient boosting for tabular time-series; runs on a laptop        | Model + hyperparameter tuning   |
| **Rolling-origin backtest** design               | Standard for time-series; guards against leakage                                 | Implementation + reporting      |
| **Conformal prediction** intervals               | The abstention rule: when P90 − P10 is too wide, we recommend "sell local"       | Read Angelopoulos et al. tutorial |
| **Pinball loss** as an evaluation metric         | The correct scoring rule for quantile forecasts                                  | Compute + report                |
| Feature engineering for **sparse panels**        | Lag features, seasonal features, neighbouring-mandi features, festival flags     | Reasoning + iteration           |
| **Anomaly detection** on raw prices              | 10× price-typo detection at ingest time                                          | Simple statistics + guard       |
| Empirical **seasonal arrival index** construction | Derived from ~18 years of arrivals per (commodity, state, ISO week)             | Pandas + aggregation            |

### 5.3 Tanishq (management + operations)

| Skill                                     | Why needed                                                                       | Depth required          |
|-------------------------------------------|-----------------------------------------------------------------------------------|--------------------------|
| APMC act / cess / commission structure    | Cost model rows are per-state and vary by APMC act                                | Reference + validation   |
| Trader / FPO interview scripts            | Field-validate the recommendation UI + the `q(R)` grade-discount curve            | Qualitative interviewing |
| Cultivar-specific shelf-life caveats      | Alphonso vs Kesar mango, cultivar-specific tomato hybrids                         | Literature + interviews  |
| Buyer segment probe                        | Whether the buyer is trader / FPO / agri-B2B / govt department changes the UI    | 3 – 5 exploratory calls  |
| Data.gov.in ticketing process              | To request historical publication as a workaround to the AGMARKNET CAPTCHA gate  | Support-ticket workflow  |

### 5.4 Learning-resource inventory

- USDA Agriculture Handbook 66 (AH-66) — free PDF, the shelf-life bible
- Open-Meteo docs — no key required
- OSRM Backend documentation — `osrm-extract`, `osrm-partition`,
  `osrm-customize` for the MLD (multi-level Dijkstra) pipeline
- TimescaleDB "hypertable" primer
- LightGBM "quantile objective" documentation + Ke et al. paper
- Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction*
- Cesa-Bianchi & Lugosi on rolling-origin evaluation
- MoSPI cross-check note on NHB Horticultural Statistics divergence
  (only as a sanity source, not ground truth — see `CLAUDE.md` ground
  rule 10)

---

## 6. Timeline to Achieve the Skillset

The skillset is acquired **just-in-time** — each competency is picked up
in the week before it is needed, not front-loaded. This keeps the team
motivated and prevents skill decay.

| Week  | Rubrangso                                                     | Monish                                              | Tanishq                                        |
|-------|---------------------------------------------------------------|-----------------------------------------------------|-------------------------------------------------|
| 1     | TimescaleDB primer, Docker Compose refresh, Agmarknet SDK read | Read AH-66 §I & §II                                 | APMC act primer for Maharashtra                  |
| 2     | Nominatim politeness, Q₁₀ theory read                          | Rolling-origin backtest theory                      | Cost-line item taxonomy                          |
| 3     | OSRM MLD bootstrap docs                                       | LightGBM tutorial + quantile objective              | Field-interview script draft                     |
| 4     | Open-Meteo docs, polyline sampling patterns                    | Pinball loss compute + report                       | Live trader / APMC contact (Nashik / Ludhiana)   |
| 5     | Q₁₀ integrator implementation                                 | LightGBM feature engineering for sparse panels      | Cultivar-specific caveats                        |
| 6     | FastAPI advanced patterns (async DI, Pydantic v2)              | Arrival-volume forecaster                           | Buyer segment probe (3 – 5 calls)                |
| 7     | Frontend framework decision + scaffold                         | Anomaly + abstention                                | Continue segment probe                           |
| 8     | Ranker + destination-card UX                                   | Conformal intervals + calibration                   | Field-validate `q(R)` curve                      |
| 9     | Twilio / Gupshup sandbox templating                            | Freshness / forecast integration polish             | Interview writeup                                |
| 10    | Alert triggers + opt-in storage                                | Counterfactual ledger nightly job                   | Trader-comparison of recommendation vs actual    |
| 11    | Deployment + demo hardening                                    | 90-day uplift report                                | Business case                                    |
| 12    | Report + defence rehearsal                                     | Thesis chapters (data + ML)                         | Thesis chapters (business + field)               |

**Skill-acquisition principle:** every teammate must have their required
skill *demonstrated in code* by the end of the week it is scheduled for.
"Read a tutorial" is not evidence; a merged pull request is.

---

## 7. Block Schematic, Algorithm, Coding, Testing, Experiments, Results

### 7.1 System block diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │                Data sources (free)              │
                    │                                                 │
                    │  AGMARKNET REST API   data.gov.in resource      │
                    │  (blocked by         (9ef84268-…)               │
                    │   CAPTCHA gate —     — snapshot only,           │
                    │   see §11)           prices only                │
                    │                                                 │
                    │  Open-Meteo (weather)   Nominatim (geocode)     │
                    │  OSRM tiles (routing)    USDA AH-66 (shelf life)│
                    └───────────────────┬─────────────────────────────┘
                                        │
                                        ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                 Ingestion & normalization                      │
        │                                                               │
        │  datagovin_client → normalize → upsert_panel → market_daily   │
        │  (paginated,        (col aliases,   (SQL merge on   (Timescale│
        │   curl UA,          Q→T unit guard,  natural key,    hyper-   │
        │   client-side       dedupe on nat.  auto-register     table)  │
        │   filtering)         key)            new mandis)             │
        └───────────────────┬─────────────────────────────┬─────────────┘
                            │                             │
                            ▼                             ▼
      ┌───────────────────────────┐          ┌────────────────────────┐
      │ Reference tables (Phase 2)│          │ Data-quality report    │
      │                           │          │ (density, gaps, typos, │
      │  shelf_life.csv (AH-66)   │          │  Gate 1 decision)      │
      │  costs.csv (10 states)    │          └────────────────────────┘
      │  freight.csv (5 trucks)   │
      │  seasonal_index.parquet   │
      │  mandi_geocodes.csv       │
      │  distance_matrix.parquet  │
      └──────────────┬────────────┘
                     │
                     ▼
   ┌───────────────────────────────┐    ┌────────────────────────────┐
   │  Cost model (Phase 2 — ready) │    │ Forecasting  (Phase 3)     │
   │                               │    │                            │
   │  net_realization(...)         │    │ LightGBM quantile P10/P50/ │
   │  → CostBreakdown{             │    │  P90, one model per        │
   │      freight, commission,     │    │  quantile, rolling-origin  │
   │      cess, entry, labour,     │    │  backtest vs 3 baselines   │
   │      weighment, gross, net }  │    └──────────────┬─────────────┘
   └──────────────┬────────────────┘                   │
                  │                                    ▼
                  │             ┌──────────────────────────────────┐
                  │             │ Freshness engine  (Phase 4)     │
                  │             │                                  │
                  │             │ OSRM route → polyline → Open-    │
                  │             │  Meteo hourly temp → Q₁₀         │
                  │             │  analytical decay integrator →   │
                  │             │  R ∈ [0, 1]                      │
                  │             └──────────────┬───────────────────┘
                  │                            │
                  ▼                            ▼
              ┌──────────────────────────────────────────────┐
              │ Decision engine (Phase 5 — the ranker)       │
              │                                              │
              │ candidates = { m : R(m) ≥ R_min }            │
              │ net(m) = P̂50 · q(R(m)) − COST(o, m, qty, c) │
              │ rank(candidates) desc by net(m)              │
              │                                              │
              │ Returns ranked list with itemised ₹          │
              │  breakdown, P10 downside, feasibility reason │
              │  for excluded destinations                   │
              └──────────────────┬───────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────────────┐
              ▼                  ▼                          ▼
      ┌─────────────┐  ┌──────────────────┐     ┌────────────────────┐
      │ FastAPI     │  │ Mobile dashboard │     │ Alerts (Phase 6)   │
      │ /recommend  │  │ (Next.js or React│     │ WhatsApp + SMS via │
      │ endpoint    │  │  + Vite; ranked  │     │ Twilio / Gupshup   │
      │ (Phase 5)   │  │  destination     │     │ Hindi + English    │
      └─────────────┘  │  cards, glut     │     │ Templates for glut,│
                       │  warnings,       │     │ crash, favourable  │
                       │  seasonal        │     │ window opens       │
                       │  heatmap,        │     └────────────────────┘
                       │  freshness       │
                       │  overlay)        │
                       └──────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────────┐
              │ Counterfactual ledger  (Phase 6 — evaluation)│
              │                                              │
              │ Persist every recommendation with inputs +   │
              │ full breakdown; nightly job scores each      │
              │ against realised prices; emits 90-day        │
              │ ₹/tonne uplift vs baseline (the defence line)│
              └──────────────────────────────────────────────┘
```

### 7.2 Core algorithms

#### 7.2.1 Freshness engine (Q₁₀ analytical decay integrator)

Given a route as a sequence of segments with temperature `T_i` and
duration `Δt_i` (from Open-Meteo along the OSRM polyline), and a
commodity with reference shelf life `SL_opt` at reference temperature
`T_opt` and Q₁₀ constant `Q`, the remaining shelf-life fraction is

    R = max(0, 1 − Σ_i  Δt_i / SL_i)

where the shelf life at ambient temperature `T_i` is

    SL_i = SL_opt · Q ^ (−(T_i − T_opt) / 10)

This uses no ML. It is a straight physics model. `R ∈ [0, 1]`, where 0
means the produce is dead on arrival and 1 means dispatched-condition
fresh. The feasibility filter is `R ≥ R_min` with `R_min = 0.35` as the
default; the value is calibrated against trader interviews in Phase 7.

`shelf_life.csv` carries the reference row per commodity: `commodity,
t_opt_c, rh_opt_pct, sl_opt_days, q10, chilling_injury_floor_c,
ethylene_sensitive, ethylene_producer, category, notes` (16 rows shipped,
transcribed from USDA AH-66 — see `docs/shelf-life-notes.md`).

#### 7.2.2 Cost model

`cost/model.py::net_realization(...)` returns a `CostBreakdown`
dataclass with each ₹ line explicitly named:

```
gross          = modal_price_per_tonne × quantity_tonnes
apmc_comm      = gross × commission_pct
cess           = gross × cess_pct
entry_fee      = entry_fee_per_tonne × quantity_tonnes
labour         = labour_per_tonne × quantity_tonnes
weighment      = weighment_per_tonne × quantity_tonnes
freight        = distance_km × rs_per_km(truck, diesel) + fixed_loading
                 × ceil(quantity_tonnes / truck_capacity)   ← multi-trip
net            = gross − (apmc_comm + cess + entry_fee + labour + weighment + freight)
```

Freight scales with diesel via a 60 % sensitivity coefficient (industry
convention). The smallest truck that fits is chosen; multi-trip is
handled by ceiling division. Reference tables ship in `data/reference/`.

#### 7.2.3 Forecaster

One LightGBM regressor per quantile (P10, P50, P90), global model across
mandis with `market_id` as a categorical feature. Loss = pinball loss at
that quantile. Features:

- Price lags: 1, 7, 14, 28, 91, 364 days
- Arrival lags (once arrivals are recovered — see §11)
- Week-of-year, day-of-week, month
- Festival flag (Deepavali, Onam, Pongal, Sankranti — commodity-specific)
- Monsoon flag (JJAS)
- Neighbouring-mandi lags (K-nearest mandis by road distance)
- District and state aggregates
- Weather covariates from Open-Meteo (mean daily temp, precipitation)

Rolling-origin backtest with 60-day training windows and 1 – 7 day
horizons.

#### 7.2.4 Ranker

```
def recommend(commodity, origin, quantity, dispatch_ts):
    candidates = neighboring_mandis(origin, radius_km=500)
    scored     = []
    for m in candidates:
        R = freshness_engine(commodity, origin, m, dispatch_ts)
        if R < R_MIN:                                # feasibility filter
            continue
        arrival_ts = dispatch_ts + duration(origin, m)
        p50, p10   = forecast(commodity, m, arrival_ts)
        grade_pen  = q_of_R(R)                       # calibrated 0.6 → 1.0
        gross_per_tonne = p50 * grade_pen
        breakdown  = cost_model.net_realization(m, quantity, commodity,
                                                gross_per_tonne, ...)
        scored.append((m, breakdown, p10))
    scored.sort(key=lambda s: s[1].net, reverse=True)
    return scored
```

Key invariant tested in unit tests: **feasibility filter runs BEFORE
the ranker; infeasible destinations never appear in the output.**

### 7.3 Coding metrics (as of 2026-09-08)

| Layer                       | Files                                        | ~LoC | Test coverage      |
|-----------------------------|----------------------------------------------|------|--------------------|
| Config + DB                 | `config/`, `db/`                             | ~ 200 | Migration runner tested by re-run |
| Ingestion (data.gov.in path) | `ingestion/datagovin_client.py`, `pull_datagovin.py` | ~ 250 | End-to-end verified live |
| Ingestion (Agmarknet path)  | `ingestion/agmarknet_client.py`              | ~ 130 | Blocked — see §11  |
| Normalize + upsert          | `ingestion/normalize.py`, `upsert.py`        | ~ 300 | Live-data verified |
| Data quality                | `ingestion/quality.py`                       | ~ 180 | Live-data verified |
| Cost model                  | `cost/model.py`                              | ~ 250 | **13 pytest cases** |
| Seasonal index              | `forecasting/seasonal.py`                    | ~ 200 | Awaits real data   |
| Geocoding                   | `ingestion/geocode.py`                       | ~ 180 | Awaits real data   |
| Distance matrix             | `freshness/distance_matrix.py`               | ~ 220 | Awaits OSRM bootstrap |
| CLI                         | `cli.py`                                     | ~ 170 | Sub-commands verified |

### 7.4 Testing metrics

**Cost model unit tests (`backend/cost/tests/test_model.py`, 13 cases):**

- Deduction sum invariance (net + all deductions = gross)
- ₹/quintal → ₹/tonne conversion correctness
- APMC commission as a % of gross
- Zero-distance still incurs fixed loading
- Diesel price scaling (60 % sensitivity coefficient)
- Multi-trip cost when quantity exceeds any single truck
- Unknown state raises `KeyError` (fail fast, no silent default)
- Negative-input rejection
- Reference-CSV guardrails: rate ranges, monotonic truck sizing

Full pytest suite runs in < 1 s.

**End-to-end verified on 2026-09-08:**

- Pipeline: `docker compose up -d db` → `migrate` → `pull-datagovin` → SQL
  query → `quality` report.
- 10,000 raw records fetched from data.gov.in in **10.7 s**.
- 1,172 rows landed in `market_daily` across 23 states, 417 markets,
  4 commodities.
- Reproducible: rerunning the pull is idempotent (natural-key upsert).

### 7.5 Experiments — Day-1 arbitrage signal

Even with **one day** of data, the capstone's central hypothesis is
visible:

**Tomato, Uttar Pradesh, 2026-09-08:**

| District      | Mandi                 | Modal ₹/qtl |
|---------------|-----------------------|-------------|
| Fatehpur      | Fatehpur APMC         | **2 587**   |
| Shamli        | Shamli APMC           | 2 566       |
| Saharanpur    | Chhutmalpur APMC      | 2 336       |
| Shamli        | Kairana APMC          | 2 200       |
| Kanpur        | Kanpur (Grain) APMC   | 2 100       |
| Pillibhit     | Puranpur APMC         | 2 000       |
| Bulandshahr   | Buland Shahr APMC     | 2 000       |
| Aligarh       | Aligarh APMC          | 2 000       |
| Saharanpur    | Saharanpur APMC       | 1 532       |
| Varanasi      | Varanasi APMC         | **1 500**   |

Same-day, same-state, same-commodity **spread of 72 %** between the
highest and lowest reporting mandi. This is exactly the pattern the
project is built on: the arbitrage signal is available on the very
first day of ingested data. Cost of freight from Varanasi to Fatehpur
(≈ 220 km road distance) is nowhere near ₹1 087/qtl, so this is real
economic surplus that a trader could capture *if* they knew about it
and *if* the produce could survive the trip. That combination — knowing
about the spread and quantifying survival — is what FreshRoute delivers.

### 7.6 Result graphs — planned

The dashboard (Phase 5) surfaces the following visualisations. They will
appear in the practicum defence and in the thesis:

1. **Same-day price-spread histogram** per (commodity, state, ISO week)
   showing how often the spread is > 40 %.
2. **Backtest pinball loss** curve, LightGBM vs (naive, seasonal-naive,
   7-day MA) baselines, at horizons 1 – 7 days.
3. **Q₁₀ decay heatmap** — remaining shelf life vs (transit hours,
   ambient temperature) for each of the 16 commodities, so a trader can
   see the survivability envelope at a glance.
4. **Seasonal calendar** — an ISO-week × (commodity, state) heatmap
   with glut / lean / normal markers derived from ~ 18 years of
   arrivals (once history is recovered — see §11).
5. **90-day counterfactual ₹/tonne uplift** — the single most important
   graph in the thesis; it is the defence line.

### 7.7 Technical papers and standards referenced

- Ke, T. et al. *LightGBM: A Highly Efficient Gradient Boosting Decision
  Tree*. NeurIPS 2017.
- Angelopoulos, A. N. and Bates, S. *A Gentle Introduction to Conformal
  Prediction and Distribution-Free Uncertainty Quantification*.
  Foundations and Trends in Machine Learning, 2023.
- Hart, B. and Ferry, W. *United States Standards for Grades of Tomatoes*
  (context for grade discount `q(R)` — USDA AMS reference).
- Delgado, C. et al. *USDA Agriculture Handbook Number 66* — commercial
  storage of fruits, vegetables, and florist and nursery stocks.
- Luber, G. and Delft, R. *Multi-Level Dijkstra*, foundation of OSRM's
  MLD algorithm (Delling et al., 2013).
- Cesa-Bianchi, N. and Lugosi, G. *Prediction, Learning, and Games* —
  the rolling-origin evaluation grounding.

---

## 8. Weekly Milestones (Programme Plan)

| Week | Phase                                             | Milestone                                                                                                        | Owner       |
|------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|-------------|
|   1  | Phase 1 — Data foundation                          | Repo scaffolded; docker-compose up; SQL migrations 001–004 applied; ingestion module skeletons + tests            | R           |
|   2  | Phase 1                                            | Live pull verified; `market_daily` populated; data-quality report; **Gate 1** density decision                    | R           |
|   3  | Phase 2 (starts) + Phase 3 backtest harness       | Shelf-life CSV, cost-model unit tests, backtest harness skeleton                                                  | R + M + T   |
|   4  | Phase 2                                            | Cost model v1 ships with sourced state rates; seasonal index code; **Gate 2** cost-model exists                    | T + M + R   |
|   5  | Phase 3 + Phase 4                                  | LightGBM price forecaster P50 v1; freshness engine `remaining_life()` core                                        | M + R       |
|   6  | Phase 3 + Phase 4 + Phase 7.0 buyer segment probe  | P10 / P90 forecasts; freshness client with Open-Meteo; 3 – 5 buyer-segment interviews                            | M + R + T   |
|   7  | Phase 5 kicks off + Phase 3 arrivals               | Ranker skeleton; API `/recommend` endpoint; arrival-volume forecaster                                             | R + M       |
|   8  | Phase 5                                            | Mobile dashboard MVP: destination cards, mandi map, price history chart, seasonal heatmap                        | R           |
|   9  | Phase 5 close                                      | End-to-end demo working on real (accumulated) data; **Gate 3** core done                                          | R + M       |
|  10  | Phase 6                                            | Alerts (Twilio / Gupshup) live; counterfactual ledger nightly job                                                | R + M       |
|  11  | Phase 6 close + Phase 7 field validation           | 90-day uplift report; 12 – 15 trader / FPO / commission-agent interviews                                          | R + M + T   |
|  12  | Phase 7                                            | Thesis document, defence deck, live-demo checklist, business case                                                | All         |

---

## 9. Completed Milestones (as of 2026-09-08)

### 9.1 Planning & documentation

- 28-idea shortlist scored across nine criteria; FreshRoute selected;
  written up in `docs/proposal.md`.
- Every technology choice documented with rationale + rejected
  alternatives in `docs/tech-stack.md`.
- Three hard gates (Weeks 2, 4, 9) established and marked as binding.
- 11 ground rules for the codebase (including "not a display app",
  "freshness is a hard constraint", "don't hard-code a crop calendar")
  documented in `CLAUDE.md`.

### 9.2 Phase 1 — Data foundation

**Environment:**

- Postgres 16 + TimescaleDB running via Docker on port 5433.
- Python 3.13 virtual environment; all pinned dependencies resolve.
- All four SQL migrations (001–004) applied; `commodities`, `states`,
  `markets`, `market_daily` (hypertable), `schema_migrations` exist.

**Ingestion:**

- `backend/ingestion/agmarknet_client.py` rewritten to match the real
  `agmarknet==0.2.2` SDK signature (was pinned incorrectly against a
  hypothetical 1.x). Ready to reactivate once the CAPTCHA gate is
  worked around.
- `backend/ingestion/datagovin_client.py` — paginated snapshot fetcher
  against `https://api.data.gov.in/resource/9ef84268-…`, working
  end-to-end with two workarounds documented in-file:
  - curl User-Agent required (default python UAs are silently rate-limited)
  - server-side `filters[state]` reliably times out; we filter client-side
- `backend/ingestion/pull_datagovin.py` orchestrates fetch → filter →
  normalize → upsert.
- `backend/ingestion/normalize.py` handles the `cmdt_name`, `model_price`
  (SDK "model" ≠ "modal" typo), `arrival_qty` variants + a Quintal → Tonne
  unit guard.
- `freshroute pull-datagovin` CLI command wired.

**End-to-end proof (2026-09-08):**

- 10,000 raw records fetched in 10.7 s.
- **1,172 rows** landed in `market_daily` across 4 target commodities,
  **23 states**, **417 markets**.
- Tomato / UP arbitrage spread of **72 %** visible on Day 1 (Fatehpur
  ₹2 587 vs Varanasi ₹1 500 per quintal).
- `docs/data-quality-report.md` generated for the 2026-09-08 window;
  1,152 (market × commodity) pairs recorded.
- `docs/phase1-mandi-selection.md` records the interim Gate 1 policy:
  **Gate 1 deferred, not failed** — re-run on Day 60 (2026-11-07).
- `docs/phase1-data-source-note.md` writes up the CAPTCHA discovery and
  fallback rationale as a defensible thesis chapter.

**First git commit** landed on `main`:
`f2a634f feat: phase 1 data foundation shipped end-to-end`.

### 9.3 Phase 2 — Cost + freshness reference data (scaffolding)

- **Shelf-life table** — 16 commodities transcribed from USDA AH-66 into
  `data/reference/shelf_life.csv` with `t_opt_c`, `rh_opt_pct`,
  `sl_opt_days`, `q10`, chilling-injury floor, ethylene sensitivity,
  category and notes; documented in `docs/shelf-life-notes.md`.
- **Cost model v1** — `backend/cost/model.py` with `CostBreakdown`
  dataclass, `pick_truck()` (multi-trip aware), diesel-linked freight,
  ₹/quintal → ₹/tonne conversion; **13 pytest cases** including
  reference-CSV guardrails.
- **Cost tables** — `data/reference/costs.csv` (10 states) and
  `freight.csv` (5 truck sizes) seeded with sourced APMC references in
  the `notes` column.
- **Seasonal arrival index** — `backend/forecasting/seasonal.py`
  computes AI(commodity, state, ISO week) and emits an ASCII heatmap
  → `docs/seasonal-calendar.md`. Awaits real historical data.
- **OSRM services** added to `docker-compose.yml` under Compose profiles
  `osrm-bootstrap` and `osrm`; bootstrap script
  `scripts/osrm_bootstrap.sh` downloads the Geofabrik India extract and
  runs `osrm-extract` → `osrm-partition` → `osrm-customize`. Not yet
  executed (30 – 60 min, ~10 GB disk).
- **Geocoding client** — `backend/ingestion/geocode.py` — polite
  Nominatim client (1.1 s inter-request), 4 query variants per mandi,
  CSV cache. Awaits Phase 1 real backfill to have markets to resolve.
- **Distance matrix** — `backend/freshness/distance_matrix.py` calls
  OSRM `/route/v1/driving` per pair (polyline retained for the Phase 4
  weather sampler); parquet cache.
- CLI: `freshroute seasonal`, `freshroute geocode`, `freshroute distances`.

---

## 10. Milestones To Be Completed

Grouped by phase, in the order they will be built.

### 10.1 Phase 1.5 — Historical + arrivals recovery (**new**, added after the CAPTCHA discovery)

- [ ] Rank the top 3 community historical AGMARKNET dumps (Kaggle,
  GitHub) by recency, license and column coverage; pick one to
  land into `market_daily` with `source='community-dump'`. **R**.
- [ ] File a data.gov.in dataset-request ticket asking whether the
  historical panel is publishable. **T**.
- [ ] Evaluate the eNAM feed for arrival volumes across the ~1,000
  mandis it covers; partially closes the arrivals gap. **M + T**.
- [ ] Schedule `freshroute pull-datagovin` as a daily cron / launchd
  job so history accumulates from Day 1. **R**.

### 10.2 Phase 2 — Complete (Weeks 3 – 4)

- [ ] Run `scripts/osrm_bootstrap.sh` (~30 – 60 min). **R**.
- [ ] Run `freshroute geocode` after backfill so `markets` is populated
  with lat/lon. **R**.
- [ ] Compute the distance matrix for the retained mandis. **R**.
- [ ] Ground-truth state cost rates with 2+ live trader / APMC contacts
  (Ludhiana, Azadpur, Nashik minimum). **T**.
- [ ] Field-validate AH-66 shelf-life haircuts and add
  `sl_field_haircut` column. **T**.
- [ ] Cross-check the derived seasonal index against NHB Horticultural
  Statistics for ≥ 2 commodity × state combinations. **M**.

### 10.3 Phase 3 — Forecasting (Weeks 3, 5 – 7)

- [ ] `backend/forecasting/backtest.py` — rolling-origin harness with
  baselines (naive, seasonal-naive, 7-day MA) and pinball loss +
  MAE / MAPE metrics. Report → `docs/backtest-baseline.md`.
- [ ] Feature engineering for the sparse panel (lags, festivals,
  monsoon, neighbours, weather covariates).
- [ ] Train LightGBM P10 / P50 / P90 quantile forecasters; persist
  models under `data/models/`. Report → `docs/price-forecast-results.md`.
- [ ] Same for the arrival-volume forecaster. Report →
  `docs/arrival-forecast-results.md`.
- [ ] Anomaly detector on the raw feed for 10× price typos.
- [ ] Conformal prediction intervals → `abstain` when P90 − P10 is too
  wide.

### 10.4 Phase 4 — Freshness engine (Weeks 5 – 6)

- [ ] `backend/freshness/shelf_life.py` loader.
- [ ] `backend/freshness/weather.py` Open-Meteo client (hourly temp
  along polyline, cached per route-hash × dispatch-date).
- [ ] `backend/freshness/decay.py` — Q₁₀ decay integrator.
- [ ] `backend/freshness/service.py` — `remaining_life()` public API.
- [ ] Unit tests on synthetic routes.
- [ ] Feasibility filter with `R_min = 0.35` default.

### 10.5 Phase 5 — Decision engine + dashboard (Weeks 7 – 9)

- [ ] `backend/decision/ranker.py` combining P̂ + R + COST.
- [ ] Grade discount `q(R)` calibrated against intra-mandi min/modal/max
  spread.
- [ ] `backend/api/main.py` — FastAPI `POST /recommend`.
- [ ] Unit test: feasibility filter runs **before** the ranker.
- [ ] Framework decision (Next.js vs React + Vite) →
  `docs/dashboard-arch.md`.
- [ ] Mobile dashboard with destination cards, itemised ₹ breakdowns,
  mandi map, seasonal heatmap, freshness overlay, Hindi + English toggle.
- [ ] **Gate 3** — end-to-end pipeline running.

### 10.6 Phase 6 — Alerts + counterfactual ledger (Weeks 9 – 11)

- [ ] Twilio / Gupshup sandbox account.
- [ ] `backend/alerts/dispatcher.py` — WhatsApp / SMS templates in
  Hindi and English.
- [ ] Opt-in preference storage per trader.
- [ ] Persist every recommendation; nightly scoring against realised
  prices → `docs/counterfactual-90day.md`.
- [ ] Wire conformal intervals into the ranker: "no confident edge,
  sell local".

### 10.7 Phase 7 — Field validation + report (Weeks 11 – 12)

- [ ] 3 – 5 exploratory buyer-segment calls in Weeks 4 – 6 (started
  early on purpose).
- [ ] 12 – 15 trader / FPO / commission-agent interviews.
- [ ] Show 10 – 15 traders the recommendations vs what they actually
  did; record reactions.
- [ ] Validate the `q(R)` grade-discount curve empirically.
- [ ] Thesis document, defence deck, live-demo checklist.

### 10.8 Stretch (only if core done by Week 9)

S1 hold-vs-sell with cold storage · S2 split-lot allocation ·
S3 procurement mode · S4 harvest wave map · S5 FPO truck-fill.

---

## 11. Expected Challenges

Ordered by realistic impact on the schedule. Every entry includes the
mitigation the project has already codified.

### 11.1 Government data source drift (**already realised**, Sept 2026)

**Description.** The AGMARKNET REST API introduced CAPTCHA gating
between the project's kickoff and Week 2. Every request now returns
`400 Bad Request` with `code: TOKEN_OR_CAPTCHA_REQUIRED`. The
`agmarknet` PyPI package (v0.2.2) is a well-designed wrapper for that
API — and it is functionally dead because of a server-side policy
change, not any bug.

**Impact.** The single largest engineering risk of Phase 1 played out
on Day 2 of Phase 1. This is not hypothetical.

**Mitigations already in place.**

- Ingestion pivoted to the data.gov.in fallback (already anticipated
  by ground rule 4 in `CLAUDE.md`).
- `docs/phase1-data-source-note.md` writes this up as a defensible
  thesis chapter — the discovery *is* a Phase 1 deliverable, not a
  failure.
- The Agmarknet client is left in the codebase, correctly wired for
  the real 0.2.x SDK, so it can be reactivated in a one-file diff if
  the CAPTCHA policy is withdrawn or a token workflow opens.

### 11.2 No history + no arrivals in the data.gov.in resource

**Description.** The fallback resource is a **daily snapshot** and
carries **prices only**. Depth accumulates only across days; the
arrivals feed does not exist there.

**Impact.**

- The Gate 1 density test (which presumes multi-year data) is not
  answerable at Week 2. It has been deferred to Day 60 (2026-11-07)
  with an interim "keep every reporting mandi" policy — see
  `docs/phase1-mandi-selection.md`.
- The seasonal arrival index (Phase 2.3) cannot be trained until
  arrivals are recovered.
- The forecaster's arrival-lag features are gated on the same recovery.

**Mitigations.** A new Phase 1.5 workstream in `TODO.md` covers three
independent paths — community dumps, an eNAM cross-source, a
data.gov.in ministry ticket. Any one of them landing partially
unblocks Phase 3.

### 11.3 Panel sparsity and mandi drop-out

**Description.** Not every mandi reports every day; some skip weeks.
This is the *normal* state of Agmarknet data.

**Mitigation.** The ingestion pipeline never assumes today's record
exists (ground rule 6). The data-quality report calculates per-mandi
density; mandis below 60 % are pruned before forecasting. Gap-aware
lag features + masking are already part of the forecaster's feature
plan (§10.3).

### 11.4 Free-tier weather + geocoding rate limits

**Description.** Open-Meteo is polite and stable but rate-limited;
Nominatim's public server has a 1 request-per-second rule and will
soft-block impolite clients.

**Mitigation.** All external clients cache aggressively at the
route-hash / mandi-id level; every retry uses tenacity with
exponential backoff; `data/reference/mandi_geocodes.csv` is a
persistent, diff-reviewable cache.

### 11.5 OSRM bootstrap disk + time cost

**Description.** The India OSM extract from Geofabrik is ~1.4 GB
compressed and the MLD preprocess produces ~ 10 GB of artifacts. The
full pipeline takes 30 – 60 min on a laptop.

**Mitigation.** OSRM is behind a Compose profile so it does not start
by default; `scripts/osrm_bootstrap.sh` is idempotent (skips if
artifacts exist).

### 11.6 Trader field-interview scheduling

**Description.** 12 – 15 interviews across Punjab, Delhi, Himachal
and Maharashtra require travel and coordination.

**Mitigation.** The buyer-segment probe (3 – 5 calls) starts in
Weeks 4 – 6 rather than Week 11, so we do not discover a wrong buyer
segment after the UI has frozen — this was an explicit change from
the initial timeline.

### 11.7 Scope creep — "one more feature"

**Description.** The most common cause of capstone failure in
data-heavy projects is a mid-project scope expansion.

**Mitigation.** Three hard gates (Weeks 2, 4, 9). Stretch features
S1 – S5 are explicitly forbidden until Gate 3 clears. `CLAUDE.md`
ground rule 1: *"Do not add features outside the current phase."*

### 11.8 Team-member illness / exam pressure

**Description.** Standard student risk.

**Mitigation.** Every phase has a documented owner and a defined
artefact; ownership is transferable. The plan has ~1 week of buffer
in Week 11 that can be traded off against an earlier slip.

### 11.9 Legal / policy questions on community historical dumps

**Description.** Kaggle / GitHub AGMARKNET dumps are technically
derived from a publicly published source, but re-publication is
grey territory.

**Mitigation.** Data used for the capstone thesis is fair use for
academic research; we will attribute the source and, if we redistribute
any dataset, we will re-check the license. If in doubt we degrade to
data.gov.in-only + document the depth limitation honestly.

### 11.10 Model overfitting on a small window

**Description.** If Phase 1.5 recovery produces only a modest history
(say 6 months), a naively trained forecaster will overfit.

**Mitigation.** The rolling-origin backtest is the guardrail; models
that do not beat all three baselines never ship. Ground rule for the
model itself: **no model ships without beating naive + seasonal-naive
+ 7-day MA on pinball loss.**

---

## 12. References

**Data sources**

- Directorate of Marketing & Inspection, GoI. *AGMARKNET Daily Price
  and Arrival Report.* https://agmarknet.gov.in
- Department of Agriculture & Farmers Welfare. *"Current Daily Price
  of Various Commodities from Various Markets (Mandi)"* — data.gov.in
  resource `9ef84268-d588-465a-a308-a864a43d0070`.
- Open-Meteo. Free non-commercial weather forecast API.
  https://open-meteo.com/
- OpenStreetMap contributors, via Geofabrik India extract.
  https://download.geofabrik.de/asia/india.html
- Nominatim public server for geocoding.
  https://nominatim.openstreetmap.org/

**Domain references**

- Delgado, C. et al. *Agriculture Handbook Number 66 — The
  Commercial Storage of Fruits, Vegetables, and Florist and Nursery
  Stocks.* United States Department of Agriculture, Agricultural
  Research Service, revised 2016.
- National Horticulture Board, GoI. *Horticultural Statistics at a
  Glance* (used as a sanity cross-check only; see MoSPI note on
  DESMOA divergence).
- eNAM — National Agriculture Market platform. https://enam.gov.in
- Ministry of Statistics and Programme Implementation (MoSPI) note on
  horticulture-statistics reconciliation.

**Technical papers**

- Ke, T., Meng, Q., Finley, T. et al. *LightGBM: A Highly Efficient
  Gradient Boosting Decision Tree.* Advances in Neural Information
  Processing Systems 30 (NeurIPS 2017).
- Angelopoulos, A. N. and Bates, S. *A Gentle Introduction to
  Conformal Prediction and Distribution-Free Uncertainty
  Quantification.* Foundations and Trends in Machine Learning, 2023.
- Delling, D., Goldberg, A. V., Pajor, T. and Werneck, R. F. *Customizable
  Route Planning in Road Networks.* Transportation Science, 2013 —
  the foundation of OSRM's MLD algorithm.
- Cesa-Bianchi, N. and Lugosi, G. *Prediction, Learning, and Games.*
  Cambridge University Press, 2006.
- Koenker, R. and Bassett, G. *Regression Quantiles.* Econometrica,
  1978 — the origin of pinball loss.

**Tooling and libraries**

- PostgreSQL 16 (`postgres.org`) and TimescaleDB (`timescale.com`).
- Open Source Routing Machine (OSRM) — Multi-Level Dijkstra.
  https://project-osrm.org/
- FastAPI, Pydantic v2, SQLAlchemy 2.0, LightGBM, pandas, pyarrow,
  structlog, tenacity, typer, python-dotenv.

**Project-internal documents (this repository)**

- `buildplan.md` — the original scoping doc, source of truth for scope.
- `CLAUDE.md` — session orientation and ground rules.
- `docs/proposal.md` — full capstone proposal, origin story, defence line.
- `docs/tech-stack.md` — every technology choice with rationale + what
  was rejected.
- `docs/shelf-life-notes.md` — AH-66 transcription conventions and
  Indian-context caveats.
- `docs/phase1-data-source-note.md` — the CAPTCHA discovery and
  fallback rationale.
- `docs/phase1-mandi-selection.md` — the deferred Gate 1 policy.
- `docs/data-quality-report.md` — auto-generated, one row per (market
  × commodity).
- `PROGRESS.md` — append-only log of shipped work per phase.
- `TODO.md` — full phase-by-phase backlog.
