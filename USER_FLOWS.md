# FreshRoute — User Flows

Critical user journeys, mapped to screens and API calls. All flows must work on a mid-range Android phone on a 3G connection.

---

## Personas

**Primary: Tomato trader / FPO manager**
- Age 35–55, uses WhatsApp and UPI daily
- Android phone (4–6"), 3G/4G, outdoor use
- Speaks Hindi or regional language + broken English
- Makes ₹50,000+ decisions under time pressure at the mandi gate

**Secondary: Aggregator / logistics coordinator**
- More tech-comfortable, may be on desktop
- Needs detailed cost breakdowns for margin analysis

---

## Flow 1: "Where should I send 5 tonnes of tomatoes today?"

**Goal:** Find the best mandi in < 30 seconds, 3 taps maximum.

**Entry points:** Home screen → "Find mandis" button, or "Find" bottom tab

**Steps:**

```
Step 1: Land on /recommend
        Default values pre-filled:
          - Commodity: Tomato (most common)
          - Qty: 5 tonnes (modal)
          - Vehicle: Small truck (default)
          - Location: GPS prompt or last-used
          - Radius: 250 km

Step 2: Tap [Find mandis] — single tap if defaults are right
        → POST /recommend (with pre-filled values)
        → Loading skeleton (< 2s on 3G)

Step 3: Results appear
        → Top card: "₹9,240/tonne net at Nashik APMC"
        → User sees the decision immediately
        → Supporting: distance, spoilage %, transit time

Step 4 (optional): Tap card to expand cost breakdown
        → CostWaterfall opens inline
        → No navigation, stays on same screen

Step 5 (optional): Tap [Directions] for GPS link
        → Opens native maps app with mandi coordinates
```

**Success criteria:** Task complete in ≤ 30 seconds, zero errors.

**API calls:** `GET /recommend?origin_lat=...&origin_lon=...&commodity=Tomato&quantity_tonnes=5&vehicle=truck_small&...`

---

## Flow 2: "Will my produce survive the journey to Pune?"

**Goal:** Check feasibility of a specific route, 2 taps.

**Entry point:** Recommend results screen, or direct link from an alert

**Steps:**

```
Step 1: On /recommend results, tap the Pune APMC card
        → Expand detail view
        → Freshness section visible immediately:
          "FreshnessBar: 7 of 10 dots"
          "12% expected spoilage over 142 km"
          "Shelf life: 6d at current temp, 3.2d remaining after transit"

Step 2: Understand the answer at a glance
        → Green dot + "Feasible" = produce survives
        → Red X + "Infeasible — 28% loss exceeds 20% threshold" = avoid
        → Amber + "Marginal — borderline at current temperature" = proceed with caution
```

**API calls:** Included in the same `/recommend` response — no additional call.

---

## Flow 3: "I got a price crash warning — what should I do?"

**Goal:** Act on an alert within 1 tap to see alternatives.

**Entry point:** WhatsApp/SMS alert (Phase 6), or Alerts section in More tab

**Steps:**

```
Step 1: User receives alert:
        "⚠ Price expected to fall 18% at Pune APMC in 2 days.
         Tap to see alternatives → [freshroute.app/recommend?commodity=Tomato&avoid=pune]"

Step 2: Single tap opens /recommend with Pune pre-marked as warned
        → Results show alternative mandis ranked
        → Pune card shown with amber warning badge, deprioritized

Step 3: User picks alternative, taps Directions
```

**API calls:** Same `/recommend` — the avoid parameter is UX-only, not API-level yet.

---

## Flow 4: "What are current prices across mandis?"

**Goal:** Browse prices without a specific routing decision.

**Entry point:** "Prices" bottom tab → `/mandis`

**Steps:**

```
Step 1: /mandis loads with default commodity (Tomato)
        → Top filter bar: Commodity ▾  State ▾  [Apply]
        → Stats row: 128 mandis · Median ₹1,890 · High ₹2,587 · Low ₹800

Step 2: Scroll the card list
        → Each card shows: mandi name, modal price, relative bar
        → Tap a card → navigate to spread view for that mandi (future)

Step 3: Change filters → tap Apply → reload
```

**API calls:** `GET /markets/prices?commodity=Tomato&state=...&limit=60`

---

## Flow 5: "How much net will I make on a specific quote?"

**Goal:** Manual what-if calculation when a commission agent calls with a quote.

**Entry point:** "Costs" bottom tab → `/estimate`

**Steps:**

```
Step 1: /estimate loads with sensible defaults
        → Quote: ₹2,587/qtl, Qty: 5t, Distance: 250km, State: UP, Diesel: ₹95

Step 2: User changes quote to the agent's actual number
        → One field change, large touch target

Step 3: Tap [Estimate net]
        → CostWaterfall appears with full breakdown
        → Headline: "₹X net after deductions"
```

**API calls:** `GET /cost/estimate?quote_price_rs_per_quintal=...&...`

---

## Flow 6: "Check last week's spreads for planning"

**Goal:** Browse historical arbitrage data.

**Entry point:** "More" tab → Arbitrage, or home page "Recent spreads" section

**Steps:**

```
Step 1: /arbitrage loads
        → Filter pills: All / Tomato / Onion / Potato / Banana

Step 2: Tap a commodity filter to narrow
        → List reloads with that commodity's state-level spreads

Step 3: Tap a row → /mandis?commodity=X&state=Y to drill down
```

**API calls:** `GET /markets/arbitrage?commodity=...&limit=30`

---

## Error States

Every flow must handle these gracefully:

| Error | User-facing message | Action |
|---|---|---|
| API timeout / 5xx | "Unable to load data. Check connection." | Retry button |
| No mandis found in radius | "No mandis reporting [commodity] within [X] km. Try increasing the radius." | Radius slider |
| Commodity not in cost table | "Cost rates not available for [state] yet." | Show nearby states |
| Infeasible — all destinations spoil | "No feasible destination within [X] km for [commodity] at [temperature]°C. Consider refrigerated transport." | Show infeasible list |
| GPS denied | "Enable location or enter your district manually." | Manual text input |
| Backend down | Show last cached result with "Showing cached data from [date]" banner | — |

---

## Navigation Map

```
/                   Home — featured recommendation + KPIs + recent spreads
/recommend          Find Mandi — the core decision screen
/mandis             Price Browser — all mandis for a commodity
/estimate           Cost Estimator — manual what-if tool
/arbitrage          Spread Explorer — commodity × state arbitrage view
```

Future routes (Phase 6+):
```
/alerts             Notification preferences + recent alerts
/ledger             Counterfactual: your history vs our recommendations
```

---

## Performance Budget

| Flow | Target load time (3G) | Notes |
|---|---|---|
| Flow 1 — Recommend | < 3s end to end | RSC data fetch + client form |
| Flow 4 — Prices | < 2s | RSC, cached 60s |
| Flow 5 — Estimate | < 1s | Client-side only after initial load |
| Home | < 2s | RSC, cached 60s |

Offline: show stale data with a "last updated [X] ago" badge. Never show a blank screen.
