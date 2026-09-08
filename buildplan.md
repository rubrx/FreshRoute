# FreshRoute — Spoilage-Aware Mandi Routing & Price Intelligence

**Capstone project plan · IIIT Una · B.Tech IT 2023–27**
Rubrangso Kri (full-stack + infra) · Monish Singal (AI/ML) · Tanishq (management/ops)

Constraints this plan is written against: **3-month build**, **100% free public data**, three-person team.
(Rename the project if you like; "FreshRoute" is a placeholder.)

---

## 1. The problem in one paragraph

A trader, FPO, or aggregator holding 5–10 tonnes of tomatoes has to answer three coupled questions at once: **which mandi, which day, and will it still be sellable when it arrives?** Today he answers all three by calling two commission agents and shipping to the mandi he shipped to last time. The price spread between mandis on the same day for the same commodity is routinely 40–100%. Meanwhile 5–15% of the consignment degrades in transit because nobody models the interaction of ambient temperature, transit time, and the commodity's remaining shelf life. The two decisions are made separately, so the "best price" mandi is often the one that arrives half-rotten.

**What we build:** a decision engine that ranks candidate mandis by *expected net realization per tonne after spoilage, freight, and commission*, with a hard feasibility filter that rejects any destination the produce cannot survive.

---

## 2. Why this is not just a price-display app

Agmarknet dashboards already exist on GitHub. The differentiators, in order of importance:

1. **Freshness budget as a hard constraint**, not a footnote. Destinations are filtered *before* being ranked by price.
2. **Net realization, not headline price.** Freight, commission, cess, labour, and shrinkage are all netted out.
3. **Empirical seasonal calendar** derived from ~18 years of arrival data, not a static "tomato is a winter crop" table.
4. **Glut early warning.** Forecasting *arrivals* 3–7 days out is what predicts a price crash. Almost nobody does this.
5. **Counterfactual ledger.** Every recommendation is scored against what the user actually did, in rupees.

### The insurance policy on this project

Mandi price forecasting is genuinely hard. You may beat a seasonal-naive baseline by only 5–10% MAPE. **That does not kill the product,** because the same-day spread *between* mandis (40–100%) is far larger than your forecast error (~15%). Value comes from arbitrage visibility + cost netting + spoilage feasibility; forecasting is the tiebreaker on *when*. Say this explicitly in the thesis defense — it is the honest answer to "what if your model is mediocre."

---

## 3. Feature set

### Core (must ship in 12 weeks)

| # | Feature | What it does |
|---|---|---|
| F1 | **Destination ranker** | Ranks candidate mandis by expected net ₹/tonne with P10/P50/P90 bands |
| F2 | **Freshness budget engine** | Computes remaining shelf life along the route; hard-rejects infeasible destinations |
| F3 | **Price forecaster** | 1–7 day quantile forecasts of modal price per mandi × commodity |
| F4 | **Arrival forecaster** | 1–7 day arrival-volume forecasts; the input to glut warnings |
| F5 | **Seasonal calendar** | Per commodity × state weekly arrival index over 10+ years; glut and lean windows |
| F6 | **Glut early warning** | Alert when forecast arrival surge at a mandi implies a price crash |
| F7 | **Cost model** | Freight from live road distance × diesel-linked ₹/km, plus APMC commission, cess, entry fee, labour |
| F8 | **Counterfactual ledger** | "Our recommendation vs your default mandi: +₹X/tonne over 90 days" |
| F9 | **Alerts** | WhatsApp/SMS push in Hindi/English for crash warnings and windows |
| F10 | **Abstention** | When forecast intervals are too wide, the system says "no confident edge, sell local" |

### Stretch (only if core is done by week 9)

| # | Feature | What it does |
|---|---|---|
| S1 | **Hold-vs-sell** | With cold storage available, is storing for N days worth the rent + shrinkage? |
| S2 | **Split-lot allocation** | Split 8 t across 2 mandis to diversify risk and avoid crashing a thin local market |
| S3 | **Procurement mode** | Flip the objective: cheapest *landed* cost for a buyer instead of best realization for a seller |
| S4 | **Harvest wave map** | Cross-correlate arrival peaks across mandi clusters to trace the geographic movement of a crop through the season |
| S5 | **FPO truck-fill** | Aggregate small farmer lots into a full truck before dispatch |

**Do not attempt anything below the line before week 9.** Scope creep is the #1 killer of 12-week capstones.

---

## 4. The freshness / seasonality module (the new centrepiece)

This is what makes the project more than a forecasting notebook, and it is fully buildable from free data.

### 4.1 Shelf-life model

USDA **Agriculture Handbook 66** (*The Commercial Storage of Fruits, Vegetables, and Florist and Nursery Stocks*) is a free PDF with 138 commodity summaries covering optimal storage temperature and relative humidity, approximate storage life under optimum conditions, respiration-rate classes, chilling-injury thresholds, and ethylene sensitivity. That gives us, per commodity:

- `SL_opt` — approximate storage life at optimal temperature `T_opt`
- respiration rate class
- chilling-injury floor (relevant because "just refrigerate it" is wrong for tomatoes and bananas)

Decay does not run at a constant rate; it runs faster when hot. Model it with a **Q₁₀ temperature coefficient** (typically 2–3 for respiration):

```
rate(T) = rate_opt × Q10 ^ ((T − T_opt) / 10)
```

Then the **freshness budget** consumed on a journey is the integral of that rate over the route:

```
spent = Σ_segments  Δt_segment × rate(T_segment)
R     = 1 − spent / SL_opt          # remaining life fraction, 0..1
```

`T_segment` comes from **Open-Meteo** hourly forecasts along the OSRM route polyline. Add expected mandi dwell (unloading + auction wait) to `Δt` — produce rots in the queue too, and this is the part everyone forgets.

**Two outputs:**

1. **Hard filter.** If projected `R < R_min` (start with 0.35, tune with traders), the destination is infeasible and is dropped from the ranking with a reason shown to the user.
2. **Soft discount.** Realizable price is quality-discounted: `P_eff = P̂ × q(R)`, where `q` is a grade-discount curve.

**Honest weak point:** we cannot observe grade directly in Agmarknet. Proxy: the min/modal/max price spread within a market-day widens as grade dispersion widens, so calibrate `q(R)` against that spread. It is a defensible, data-grounded proxy, but flag it as an assumption. Tanishq validates it against trader interviews in week 11.

### 4.2 Seasonal timeline

Do **not** hard-code a crop calendar. Derive it, because the arrival data already contains it:

```
AI(commodity, state, week) = median arrivals in ISO week w over 10 yrs
                             ÷ annual median arrivals
```

- `AI > 1.5` → **glut window** (prices crash, ship far or hold)
- `AI < 0.6` → **lean window** (prices spike, ship local and fast)

Cross-check the derived calendar against **NHB Horticultural Statistics at a Glance** (state-wise area/production, plus state-wise cold storage capacity tables). One caution worth writing into the report: India's own Ministry of Statistics has noted that NHB horticulture estimates are based on subjective ground-level reports and diverge considerably from the DESMOA survey estimates. So use NHB as a **sanity cross-check only** — Agmarknet arrivals are the primary seasonality signal. Noting this in the thesis shows genuine data judgement.

### 4.3 How the two combine

The freshness engine turns a static "which mandi pays most" question into a **time-and-temperature-constrained optimization**:

```
maximize   Net(m, τ) = Q · (1 − shrink(R)) · P̂_modal(m, t+τ) · (1 − commission_m − cess_m)
                       − freight(dist_m, diesel_t) − labour − entry_fee_m
subject to R(m, τ) ≥ R_min
```

Rank by the P50 of `Net`, display the P10 as downside. That inequality is the entire product.

---

## 5. Data sources (all free, all verified)

| Source | What it gives | Access | Notes |
|---|---|---|---|
| **AGMARKNET official REST API** | Daily price **and arrival volume**, per commodity/state/district/market/variety, 2007→ | `agmarknet` package on PyPI — pandas wrapper, `data_type="both"`, auto-chunks long date ranges by year | **Primary dataset.** This is the one that carries arrivals |
| **data.gov.in — "Current daily price of various commodities from various markets (Mandi)"** | Daily min/max/modal prices, CSV/JSON + API, under NDSAP | Register for your own API key | **Prices only — no arrival volume.** Public shared key is rate-limited. Use as a live daily feed, not the history source |
| **USDA Agriculture Handbook 66** | Storage life, optimal temp/RH, respiration rates, chilling injury, for 138 commodities | Free PDF from USDA ARS (`ars.usda.gov/ARSUserFiles/oc/np/CommercialStorage/CommercialStorage.pdf`) | Basis of the shelf-life table. Transcribe ~15 commodities into a CSV by hand |
| **Open-Meteo** | Historical archive + forecast, hourly temp/humidity/rain, no key needed for non-commercial | REST API | Route temperature profile + weather covariates for forecasting |
| **OpenStreetMap (Geofabrik India extract) + OSRM** | Road distance and duration matrix between mandis | Self-host OSRM in Docker | Free forever, no Google Maps bill, no rate limit |
| **NHB Horticultural Statistics at a Glance** | State-wise area/production; state-wise cold storage capacity | Free PDFs on nhb.gov.in | Cross-check only (see §4.2). Cold-storage table feeds stretch feature S1 |
| **data.gov.in — All India / State-wise Area & Production of Horticulture Crops** | Structured area/production | NDSAP, CSV | Cleaner than the NHB PDFs for the same numbers |
| **PPAC / state fuel price pages** | Daily diesel retail price | Scrape or manual weekly | Makes the freight cost live instead of a hard-coded constant |
| **Nominatim / OSM** | Mandi lat-long | Geocode the Agmarknet market list once | Mandis don't move — cache forever |

### Known data quirks to handle in ingestion (these are part of the engineering contribution)

- Dates arrive as `DD/MM/YYYY`; normalize to ISO at ingest
- **Markets report sparsely.** There is often no record for "today" for a given market. Always show the most recent record, never assume today's
- **Multiple varieties** can appear for the same market and day — decide explicitly whether to average or keep separate
- Market renames, duplicate market names across states, and unit inconsistencies
- Irregular panel gaps: drop any mandi reporting fewer than ~60% of days in the study window

Handling this properly is a genuine contribution and should be its own section in the report.

---

## 6. Scope

- **Commodities:** tomato, onion, potato (maximum volatility + volume), plus one fruit (banana or mango) to exercise the fruit side of the shelf-life model
- **Geography:** 2–3 states, 60–100 mandis. Not all 2000+
- **Horizon:** 1–7 days, quantile forecasts
- **Users modelled:** trader / aggregator / FPO manager

---

## 7. Who does what

### Monish — AI/ML

| Task | Detail |
|---|---|
| Backtest harness **first** | Rolling-origin evaluation before any model. Baselines: naive, seasonal-naive, 7-day MA. No model ships without beating these |
| **Price forecaster** | Global LightGBM, quantile objective (P10/P50/P90), h = 1..7. Features: price and arrival lags, week-of-year, festival flags, monsoon flags, district and state aggregates, neighbouring-mandi lags, weather |
| **Arrival forecaster** | Same family. Feeds the glut warning. Arguably more valuable than the price model |
| **Seasonal index extraction** | STL decomposition + weekly arrival index per commodity × state |
| **Missing-data handling** | Sparse irregular panels. Masking, gap-aware lags, imputation strategy — write this up, it's a real contribution |
| **Grade-discount calibration** | Fit `q(R)` against intra-market min/modal/max spread |
| **Abstention** | Conformal prediction intervals → "no confident edge today" |
| Anomaly detection | Flag bad feed records (unit errors, 10× price typos) before they poison the model |

Everything here is LightGBM/scikit-learn/pandas tabular work — his actual strength. No computer vision required.

### Rubrangso — Full-stack + infrastructure

| Task | Detail |
|---|---|
| **Ingestion pipeline** | Daily scheduled pull + historical backfill, dedupe, normalize, quality checks. Airflow or a plain cron + Python service |
| **Data store** | Postgres + TimescaleDB hypertable for the price/arrival panel |
| **OSRM service** | Self-hosted on India OSM extract, plus a cached mandi-to-mandi distance/duration matrix |
| **Freshness engine** | Service that takes (commodity, origin, destination, dispatch time) → route polyline → Open-Meteo temperature profile → remaining life `R`. This is your novel service |
| **Recommendation API** | Combines forecasts + freshness + cost model → ranked destinations with breakdown |
| **Dashboard** | Mobile-first. Mandi map, price history, ranked destination cards with an itemized ₹ breakdown, seasonal calendar heatmap, glut warnings |
| **Alerts** | WhatsApp/SMS (Twilio trial or Gupshup sandbox), Hindi + English templates |
| **Counterfactual ledger** | Stores every recommendation, scores it against realized prices, reports cumulative ₹/tonne uplift |
| **Deploy** | Docker Compose, nightly batch scoring, basic auth + multi-tenant (trader / FPO) |

Note for your own career file: the ingestion pipeline, the batch scoring layer, the distance-matrix cache, and the model-serving API are the parts that read as infrastructure engineering rather than CRUD. Build them deliberately and write them up that way.

### Tanishq — Management / operations / business

| Task | Detail |
|---|---|
| **Cost model** (week 3–4, hard deadline) | Freight ₹/km by truck size, APMC commission % by state, market cess, entry fee, loading/unloading labour, weighment. Without this the ranker has no objective function |
| **Shelf-life validation** | Take the AH-66 numbers to actual traders. US cold-chain assumptions ≠ an open truck in a Punjab June. Get real-world haircuts |
| **Field interviews** | 12–15 traders / FPO members / commission agents. Reachable from Una: Una, Nurpur, Ludhiana, Solan, Delhi Azadpur contacts |
| **KPI definition** | Primary: ₹/tonne uplift vs the user's default mandi. Secondary: % of consignments arriving within shelf life |
| **Competitive scan** | Agmarknet display apps, e-NAM, Ninjacart, state agri portals. Where is the gap and is it real? |
| **Business model** | Who actually pays: individual trader vs FPO vs agri-B2B platform vs state agri department. Test this, don't assume |
| **Risk register + cost-benefit** | Quantified, in the report |

**Tanishq's role is the one most likely to decay into slide-making.** Make the cost model a hard week-4 deliverable with a due date, because the optimization objective literally cannot be written without it.

---

## 8. 12-week timeline

| Week | Deliverable | Owner |
|---|---|---|
| 1 | API keys, `agmarknet` SDK pull for 4 commodities × 3 states, raw data landed | R |
| 2 | Ingestion pipeline + TimescaleDB schema + **data quality report**. **GATE: is the panel clean and dense enough?** | R |
| 2 | AH-66 shelf-life table transcribed to CSV for chosen commodities | M + T |
| 3 | Backtest harness + baselines (naive, seasonal-naive, MA) | M |
| 3–4 | **Cost model v1** (freight, commission, cess, labour) | **T** |
| 4 | Seasonal arrival index + glut/lean calendar per commodity × state | M |
| 4 | OSRM self-hosted, mandi geocoding, distance matrix cached | R |
| 5–6 | LightGBM quantile price forecaster; must beat baselines, quantify by how much | M |
| 5–6 | Freshness engine service (OSRM route → Open-Meteo profile → Q₁₀ decay → `R`) | R |
| 6–7 | Arrival forecaster + glut early warning | M |
| 7–8 | Decision layer: feasibility filter + net realization ranker | R + M |
| 8–9 | Dashboard, seasonal heatmap, ranked destination cards | R |
| 9 | **STRETCH GATE.** Core done? Only then touch S1–S5 | all |
| 9–10 | Alerts (WhatsApp/SMS), abstention logic | R + M |
| 10–11 | Counterfactual backtest: "our recommendations vs default mandi, 90 days, ₹/tonne" | M + R |
| 11 | **Field validation:** show 10–15 traders last month's recommendations vs what they actually did | **T** |
| 12 | Report, demo, paper-trading results, defense deck | all |

---

## 9. Evaluation metrics

**Forecasting**
- MAE / MAPE and **pinball loss** for quantiles, vs naive and seasonal-naive baselines
- Report the improvement over baseline honestly, even if it's small

**Decision quality (the one that matters)**
- Backtested ₹/tonne uplift vs two counterfactual policies: (a) always ship to nearest mandi, (b) always ship to historical default mandi
- % of recommended shipments that would have arrived within shelf life vs the same for the baseline policies
- Regret: how far below the ex-post best mandi did we land

**System**
- Ingestion completeness (% of expected market-days captured)
- p95 recommendation latency
- Forecast refresh SLA

---

## 10. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Sparse mandi reporting makes the panel unusable | High | Week-2 gate. Drop mandis below 60% reporting density. Choose states with dense reporting |
| Forecast barely beats seasonal-naive | Medium | Product value rests on the spread + spoilage filter, not on forecast skill. Frame accordingly (§2) |
| Grade-discount curve `q(R)` is unvalidated | Medium | Proxy from intra-market price spread; validate with traders in week 11; report as an assumption |
| AH-66 shelf-life figures are US cold-chain figures | Medium | Apply trader-validated haircuts; treat `SL_opt` as an upper bound |
| Willingness to pay is unproven | High | Buyer is more likely an FPO, an agri-B2B platform, or a state agri department than an individual trader. Test in week 11, not month 6 |
| Scope creep into stretch features | High | Week-9 gate. Nothing below the line before then |
| Tanishq's work drifts to slides | Medium | Week-4 hard deadline on the cost model — the optimizer can't be written without it |

---

## 11. Deliverables at week 12

1. Running system: ingestion → forecasts → freshness engine → ranked recommendations → dashboard + alerts
2. Backtest report: forecast skill vs baselines, and **₹/tonne uplift over 90 days of paper trading**
3. Seasonal calendar artifact per commodity × state, derived from 10+ years of arrivals
4. Field validation writeup from 12–15 trader interviews
5. Data-engineering writeup on Agmarknet panel quirks and how they were handled
6. Business case: buyer segments, pricing, cost-benefit, competitive gap
7. Thesis document + defense deck

**The single line the whole defense rests on:** *"Over 90 days of historical backtesting across N mandis, our recommendations would have earned ₹X more per tonne than the default policy, while keeping Y% of consignments within shelf life versus Z% for the baseline."* That number is computable entirely from free historical data, which is exactly why this project works under the constraints.