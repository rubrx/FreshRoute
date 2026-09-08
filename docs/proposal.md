# FreshRoute — Capstone Proposal

**Spoilage-aware mandi routing and price intelligence for Indian agri traders**
IIIT Una · B.Tech IT 2023–27
Rubrangso Kri (full-stack + infra) · Monish Singal (AI/ML) · Tanishq (management/ops)

> One-line pitch: rank candidate mandis by expected net ₹/tonne after spoilage, freight, and commission — with a hard feasibility filter that rejects any destination the produce cannot survive.

---

## 1. Abstract

A trader, FPO, or aggregator holding 5–10 tonnes of a perishable commodity has to answer three coupled questions at once — **which mandi, which day, and will the produce still be sellable when it arrives?** They currently answer all three by calling two commission agents and shipping to the mandi they shipped to last time.

FreshRoute models these decisions jointly. The engine (a) ranks candidate destination mandis by expected net realization per tonne after netting freight, APMC commission, cess, and shrinkage; (b) applies a **hard feasibility filter** using a Q₁₀-based freshness budget computed along the actual OSRM route and hourly Open-Meteo temperatures; and (c) reports a counterfactual ledger — over a 90-day paper-trading backtest, would the recommendations have out-earned the trader's default mandi, and by how much per tonne?

The system is buildable in 12 weeks by a three-person team using **100% free public data**.

---

## 2. Problem statement

Two structural facts make this problem real:

1. **The price spread between mandis on the same day for the same commodity is routinely 40–100%** — orders of magnitude larger than any realistic forecast error.
2. **5–15% of the consignment degrades in transit** because nobody models the interaction of ambient temperature, transit time, and the commodity's remaining shelf life.

The two decisions — which mandi to ship to, and whether the produce can survive the trip — are made separately today. So the "best price" mandi is often the one that arrives half-rotten. The trader's rational response is risk aversion: they ship to whoever they know, and leave money on the table.

---

## 3. How this project was selected

This section exists so future readers understand *why* the constraints are what they are.

### 3.1 The shortlist

The team weighted-scored 28 candidate problems in the logistics / supply-chain / agri space across nine criteria (impact, AI relevance, technical depth, full-stack surface, business viability, feasibility, data access, uniqueness, real users). The initial top-ranked idea was a **Delivery Risk Engine** — COD/RTO risk prediction plus Indian address resolution for small D2C sellers.

### 3.2 What the constraints killed

Two hard constraints then narrowed the field:

- **100% free public data** — no partnerships, no NDAs, no paid APIs.
- **3-month build** with a 3-person team.

Under those constraints:

- The Delivery Risk Engine died: no free labeled Indian COD/RTO dataset exists. Without real delivery-outcome labels the classifier is synthetic-data theatre.
- Diesel-shrinkage detection, facility dwell-time scoring, near-expiry pharma redistribution, handwritten bilty OCR, and perishable newsvendor ordering all died for the same reason — they needed a data partner.
- Warehouse slotting and beat-optimization died on the 3-month clock — building a mini-WMS eats eight of twelve weeks before an ML model is touched.
- Visual defect inspection (the incumbent choice in the earlier planning file) was rejected: it plays to Monish's *weakest* area (he is a tabular ML / LightGBM / LangGraph engineer, not a CV engineer); MVTec-AD is the reference dataset for everyone building this direction, so it reads as coursework; and factory defect images cannot be sourced by students at scale.

### 3.3 Why mandi routing survives

Agmarknet publishes daily wholesale min/max/modal prices *and arrival volumes*, per commodity × state × district × market × variety, from 2007 to present. It is downloadable via the `agmarknet` PyPI package as pandas DataFrames, no API key needed for historical bulk pulls (the SDK scrapes the official portal with polite rate limiting). This gives ~18 years of real, Indian, daily, panel data for free — nothing else on the shortlist comes close.

The **runner-up considered** was the **2021 Amazon Last Mile Routing Research Challenge** dataset (3.1 GB, 9,184 real routes across five US metros). Rejected because it is US-only data with no Indian angle and no business layer for Tanishq, and its CC BY-NC 4.0 license forecloses any startup path.

### 3.4 What we deliberately are not building

A price-display app. Agmarknet dashboards already exist on GitHub. The differentiator is the **decision** (which mandi, netted for cost and decay), not the **display**. This is written into ground rule 8 in `CLAUDE.md`.

---

## 4. Why forecasting mediocrity does not kill this project

This is the single most important framing point, and the honest answer to "what if your model is only okay?"

Mandi price forecasting is genuinely hard. A global LightGBM quantile model may beat a seasonal-naive baseline by only 5–10% MAPE. **That does not kill the product**, because:

```
Same-day spread between mandis for tomato/onion:   40 – 100 %
Realistic forecast error at 1–7 day horizon:          ~15 %
Freight + commission + cess + labour deductions:   deterministic, sizeable
Freshness budget along the route:                  deterministic, hard filter
```

The forecast error is small compared to the arbitrage. Even a mediocre forecast, plugged into a decision layer that nets out transport cost, commission, and spoilage, beats what the trader does today (call two agents, ship to habit).

**Value comes from arbitrage visibility + cost-netting + spoilage feasibility. Forecasting is the tiebreaker on *when*, not the core claim.**

Every design decision — including the choice to load AH-66 shelf-life reference data before the ML model exists, and the choice to freeze the cost model at week 4 as a hard deliverable — flows from that framing.

---

## 5. The four differentiators

Ordered by importance:

1. **Freshness budget as a hard constraint**, not a footnote. Destinations are filtered *before* being ranked by price.
2. **Net realization, not headline price.** Freight, commission, cess, labour, and shrinkage are all netted out and shown as an itemized ₹ breakdown in the UI.
3. **Empirical seasonal calendar** derived from ~18 years of arrival data. `AI(commodity, state, iso_week) = median weekly arrivals ÷ weekly baseline`. Not a static "tomato is a winter crop" table.
4. **Glut early warning.** Forecasting *arrivals* 3–7 days out is what predicts a price crash. Almost nobody does this, because most Agmarknet apps only ingest prices.

And the reporting layer:

5. **Counterfactual ledger.** Every recommendation is scored against what the user actually did, in rupees. This produces the single-sentence defense claim in §10.

---

## 6. System architecture

```
    ┌────────────────────────┐        ┌───────────────────────┐
    │ Agmarknet SDK          │        │ USDA AH-66 (CSV)      │
    │ data.gov.in daily feed │        │ NHB stats (sanity)    │
    │ (prices only)          │        │ State cost tables     │
    └───────────┬────────────┘        └───────────┬───────────┘
                │ backfill + daily                │
                ▼                                 ▼
    ┌──────────────────────────┐         ┌────────────────────┐
    │ Postgres + TimescaleDB   │         │ data/reference/    │
    │ market_daily hypertable  │         │ shelf_life.csv     │
    │ (date, market, commodity,│         │ costs.csv          │
    │  variety, prices, arrival)│        │ freight.csv        │
    └──────────┬───────────────┘         └──────────┬─────────┘
               │                                    │
               ▼                                    ▼
        ┌─────────────────┐   ┌─────────────────────────┐
        │ LightGBM        │   │ Cost model              │
        │ quantile        │   │ (pure fn, ₹/tonne net)  │
        │ (P10/P50/P90)   │   └────────┬────────────────┘
        │ price + arrival │            │
        └────────┬────────┘            │
                 │                     │
                 │      ┌──────────────┴──────────┐
                 │      │ Freshness engine        │
                 │      │ OSRM route → Open-Meteo │
                 │      │  → Q₁₀ decay → R∈[0,1]  │
                 │      └──────────┬──────────────┘
                 │                 │
                 ▼                 ▼
          ┌───────────────────────────────┐
          │ Decision engine               │
          │ 1. Feasibility filter (R ≥ Rₘ)│
          │ 2. Net realization ranker     │
          │ 3. Grade discount q(R)        │
          │ 4. Abstention (conformal)     │
          └────────────┬──────────────────┘
                       │
             ┌─────────┴──────────┐
             ▼                    ▼
      ┌───────────────┐   ┌──────────────────┐
      │ FastAPI       │   │ Counterfactual   │
      │ /recommend    │   │ ledger (nightly) │
      └───────┬───────┘   └────────┬─────────┘
              │                    │
              ▼                    ▼
      ┌───────────────┐   ┌──────────────────┐
      │ Mobile        │   │ WhatsApp/SMS     │
      │ dashboard     │   │ alerts           │
      └───────────────┘   └──────────────────┘
```

The core inequality the whole system implements:

```
maximize   Net(m, τ) = Q · (1 − shrink(R)) · P̂_modal(m, t+τ) · (1 − commission_m − cess_m)
                       − freight(dist_m, diesel_t) − labour − entry_fee_m
subject to R(m, τ) ≥ R_min
```

Rank by the P50 of `Net`, display the P10 as downside.

---

## 7. Data sources (all free, all verified)

| Source | What it gives | Access | Notes |
|---|---|---|---|
| **AGMARKNET official REST API** via `agmarknet` PyPI | Daily price **and arrival volume**, per commodity × state × district × market × variety, 2007→ | Python SDK; auto-chunks long ranges by year | **Primary panel.** Arrivals matter (that is what predicts a glut). |
| **data.gov.in NDSAP mandi resource** | Daily min/max/modal prices, CSV/JSON + API | Register for your own API key (shared key is rate-limited) | **Prices only — no arrivals.** Use as live daily feed, not history. |
| **USDA Agriculture Handbook 66** | Storage life, optimal temp/RH, respiration, chilling injury, for 138 commodities | Free PDF from `ars.usda.gov` | Shipped as `data/reference/shelf_life.csv` (16 commodities). |
| **Open-Meteo** | Historical archive + forecast, hourly temp/humidity/rain | REST API, no key for non-commercial | Route temperature profile + weather covariates. |
| **OpenStreetMap (Geofabrik India) + OSRM** | Road distance and duration between mandis | Self-host OSRM in Docker | Free forever, no Google Maps bill. |
| **NHB Horticultural Statistics at a Glance** | State-wise area/production; cold storage capacity | Free PDFs at `nhb.gov.in` | **Sanity cross-check only.** MoSPI has flagged that NHB uses subjective ground-level reports and diverges from DESMOA survey estimates. Agmarknet arrivals are the primary seasonality signal. |
| **PPAC / state fuel price pages** | Daily diesel retail price | Scrape or manual weekly | Makes freight cost live rather than constant. |
| **Nominatim / OSM** | Mandi lat-long | One-time geocode of the market list | Mandis do not move — cache forever. |

### Known Agmarknet quirks (these are part of the engineering contribution)

- Dates arrive as `DD/MM/YYYY`; normalize to ISO at ingest.
- Markets report sparsely. There is often no record for "today" for a given market. Always show the most recent record, never assume today's.
- Multiple varieties can appear for the same market and day — kept in the natural key.
- Market renames, duplicate market names across states, unit inconsistencies.
- Irregular panel gaps: drop any mandi reporting fewer than ~60% of days in the study window.

Handling these properly is a genuine data-engineering contribution and will be its own section in the thesis.

---

## 8. ML approach

### 8.1 Backtest harness before any model

Rolling-origin evaluation, configurable horizon `h ∈ {1..7}`. Baselines:
- **Naive:** last known price.
- **Seasonal-naive:** same weekday last year.
- **7-day moving average.**

Rule: **no model ships without beating all three baselines.** Metrics: MAE, MAPE, pinball loss per quantile. Report the improvement over baseline honestly, even if small.

### 8.2 Price forecaster

Global LightGBM, quantile objective (one model per quantile P10/P50/P90), horizon `h = 1..7`. Features:
- Price + arrival lags (per mandi and district)
- Week-of-year, festival flags, monsoon flag
- District- and state-level aggregates
- Neighbouring-mandi lags
- Weather covariates (Open-Meteo daily aggregates)

Missing-data handling — masking, gap-aware lags, imputation strategy — will be written up as a first-class contribution.

### 8.3 Arrival forecaster

Same feature family, target = arrival volume. Feeds the glut early-warning. Arguably more valuable than the price forecaster because arrivals are what drive the crash.

### 8.4 Freshness engine (not ML)

Analytical model, no learning:

```
rate(T) = rate_opt · Q10 ^ ((T − T_opt) / 10)
spent   = Σ_segments  Δt_segment · rate(T_segment)
R       = 1 − spent / SL_opt               # remaining life fraction, 0..1
```

`T_segment` from hourly Open-Meteo along the OSRM route polyline. Add expected mandi dwell (unloading + auction wait) — produce rots in the queue too.

Two outputs:
1. **Hard filter.** If projected `R < R_min` (default 0.35), the destination is dropped with a reason.
2. **Soft discount.** `P_eff = P̂ × q(R)`, where `q` is a grade-discount curve calibrated against intra-market min/modal/max spread.

### 8.5 Abstention

Conformal prediction intervals. When P90 − P10 exceeds a threshold, surface "no confident edge — sell local."

---

## 9. Team roles

### Monish (AI/ML)

Backtest harness → baselines → LightGBM quantile forecasters → seasonal index extraction → missing-data handling writeup → grade-discount calibration → abstention. All LightGBM/scikit-learn/pandas tabular work — his actual strength.

### Rubrangso (full-stack + infrastructure)

Ingestion pipeline → TimescaleDB schema → OSRM self-hosted + distance matrix cache → freshness engine service → FastAPI recommendation endpoint → mobile dashboard → alerts → counterfactual ledger → Docker Compose deploy.

The parts that read as **infrastructure engineering rather than CRUD** (career-portfolio-wise): ingestion pipeline, batch scoring layer, distance-matrix cache, model-serving API. Build them deliberately and write them up as such.

### Tanishq (management / operations / business)

- **Cost model** (week 3–4, hard deadline). Without this the ranker has no objective function.
- **Shelf-life validation.** AH-66 numbers are US cold-chain — validate haircuts against actual Indian open-truck traders.
- **Field interviews.** 12–15 traders / FPO members / commission agents. Reachable from Una: Una, Nurpur, Ludhiana, Solan, Delhi Azadpur.
- **KPI definition.** Primary: ₹/tonne uplift vs default mandi. Secondary: % arriving within shelf life.
- **Competitive scan.** Where is the gap and is it real?
- **Business model.** Who actually pays — trader vs FPO vs agri-B2B platform vs state agri department. **Test in week 11, not month 6.**
- **Risk register + cost-benefit**, quantified, in the report.

Tanishq's role is the one most likely to decay into slide-making. The cost model is a hard week-4 deliverable with a due date, because the optimizer literally cannot be written without it.

---

## 10. 12-week timeline (with hard gates)

| Week | Deliverable | Owner |
|---|---|---|
| 1 | API access, `agmarknet` SDK pull for 4 commodities × 3 states, raw data landed | R |
| 2 | Ingestion pipeline + TimescaleDB schema + **data quality report**. 🔒 **GATE 1: is the panel clean and dense enough?** Drop mandis below 60% reporting density. | R |
| 2 | AH-66 shelf-life table transcribed to CSV | M + T |
| 3 | Backtest harness + baselines (naive, seasonal-naive, MA) | M |
| 3–4 | **Cost model v1** — 🔒 **GATE 2: exists, or the ranker has no objective function** | **T** |
| 4 | Seasonal arrival index + glut/lean calendar per commodity × state | M |
| 4 | OSRM self-hosted, mandi geocoding, distance matrix cached | R |
| 5–6 | LightGBM quantile price forecaster; must beat baselines, quantify by how much | M |
| 5–6 | Freshness engine service (OSRM route → Open-Meteo profile → Q₁₀ decay → R) | R |
| 6–7 | Arrival forecaster + glut early warning | M |
| 7–8 | Decision layer: feasibility filter + net realization ranker | R + M |
| 8–9 | Dashboard, seasonal heatmap, ranked destination cards | R |
| 9 | 🔒 **GATE 3: core done?** Only then touch stretch features S1–S5 | all |
| 9–10 | Alerts (WhatsApp/SMS), abstention logic | R + M |
| 10–11 | Counterfactual backtest: recommendations vs default mandi, 90 days, ₹/tonne | M + R |
| 11 | **Field validation:** show 10–15 traders last month's recommendations vs what they actually did | **T** |
| 12 | Report, demo, paper-trading results, defense deck | all |

---

## 11. The single line the whole defense rests on

> *"Over 90 days of historical backtesting across N mandis, our recommendations would have earned ₹X more per tonne than the default policy, while keeping Y% of consignments within shelf life vs Z% for the baseline."*

That number is computable entirely from free historical data. Which is exactly why this project works under the constraints.

---

## 12. Evaluation metrics

**Forecasting**
- MAE / MAPE and pinball loss for quantiles, vs naive and seasonal-naive baselines.
- Report the improvement over baseline honestly, even if it is small.

**Decision quality (the one that matters)**
- Backtested ₹/tonne uplift vs two counterfactual policies: (a) always ship to nearest mandi, (b) always ship to historical default mandi.
- % of recommended shipments that would have arrived within shelf life vs the same for the baseline policies.
- Regret: how far below the ex-post best mandi did we land.

**System**
- Ingestion completeness (% of expected market-days captured).
- p95 recommendation latency.
- Forecast refresh SLA.

---

## 13. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Sparse mandi reporting makes the panel unusable | High | Week-2 gate. Drop mandis below 60% reporting density. Choose states with dense reporting. |
| Forecast barely beats seasonal-naive | Medium | Product value rests on the spread + spoilage filter, not on forecast skill. Frame accordingly. |
| Grade-discount curve `q(R)` is unvalidated | Medium | Proxy from intra-market price spread; validate with traders in week 11; report as an assumption. |
| AH-66 shelf-life figures are US cold-chain figures | Medium | Apply trader-validated haircuts; treat `SL_opt` as an upper bound. |
| Willingness to pay is unproven | High | Buyer is more likely an FPO, an agri-B2B platform, or a state agri department than an individual trader. Test in week 11, not month 6. |
| Scope creep into stretch features | High | Week-9 gate. Nothing below the line before then. |
| Tanishq's work drifts to slides | Medium | Week-4 hard deadline on the cost model — the optimizer cannot be written without it. |
| Agmarknet SDK behaviour changes between versions | Medium | SDK call isolated in one wrapper module; first live pull will confirm return shape; the rest of the pipeline talks to normalized DataFrames. |

---

## 14. Deliverables at week 12

1. Running system — ingestion → forecasts → freshness engine → ranked recommendations → dashboard + alerts.
2. Backtest report — forecast skill vs baselines, and **₹/tonne uplift over 90 days of paper trading**.
3. Seasonal calendar artifact per commodity × state, derived from 10+ years of arrivals.
4. Field validation writeup from 12–15 trader interviews.
5. Data-engineering writeup on Agmarknet panel quirks and how they were handled.
6. Business case — buyer segments, pricing, cost-benefit, competitive gap.
7. Thesis document + defense deck.

---

## 15. Stretch features (only if core is done by week 9)

| # | Feature | What it does |
|---|---|---|
| S1 | Hold-vs-sell | With cold storage available, is storing for N days worth the rent + shrinkage? |
| S2 | Split-lot allocation | Split 8 t across 2 mandis to diversify risk. |
| S3 | Procurement mode | Flip the objective: cheapest landed cost for a buyer. |
| S4 | Harvest wave map | Cross-correlate arrival peaks across mandi clusters. |
| S5 | FPO truck-fill | Aggregate small farmer lots into a full truck before dispatch. |

---

## 16. What we are explicitly not building

- All 2000+ mandis (scope: 60–100 mandis across 2–3 states).
- A price-display app (Agmarknet dashboards already exist on GitHub).
- Computer vision, satellite imagery, IoT sensors.
- Live GPS truck tracking.
- Paid data sources (Google Maps distance matrix, commercial weather APIs).
- Stretch features S1–S5 before week 9.
