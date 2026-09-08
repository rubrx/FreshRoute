# Phase 1 — Data Source Note

**Author:** Rubrangso
**Date:** 2026-09-08
**Status:** Ships. Historical + arrivals gap deferred as a Phase 1.5 research item.

## TL;DR

The Phase 1 assumption — "the `agmarknet` PyPI package will give us 18 years
of daily prices and arrivals for free" — is broken. The official AGMARKNET
REST API (`api.agmarknet.gov.in/v1/daily-price-arrival/report`) now requires
a CAPTCHA on every request. We could not automate against it. Phase 1 ships
on the **data.gov.in** fallback (already anticipated by ground rule 4 in
`CLAUDE.md`), with two caveats we now own:

1. **Prices only, no arrivals.** The `arrival_qty` field does not exist in
   the data.gov.in resource. `market_daily.arrival_tonnes` will be NULL for
   all datagovin-sourced rows.
2. **Snapshot only, no history.** The endpoint publishes today's report;
   depth accumulates only by running the daily pull.

## What we discovered

### 1. The `agmarknet` SDK is blocked by a server-side CAPTCHA

Package: `agmarknet==0.2.2` (latest on PyPI, published as Alpha). Uses the
official REST API. Every `report(...)` call returns:

```
400 Bad Request
{"detail":"Captcha key and captcha value are required.",
 "code":"TOKEN_OR_CAPTCHA_REQUIRED"}
```

Confirmed with a direct request-body dump on 2026-09-08. This is a policy
change on the government side, not an SDK bug. Automated ingestion via the
official REST API is not currently possible without either (a) a
CAPTCHA-solving service — which violates the free-data constraint and adds
cost — or (b) an as-yet-undocumented API token that the government has not
opened publicly.

### 2. data.gov.in works but has two production-worthy quirks

Resource: `9ef84268-d588-465a-a308-a864a43d0070` — *"Current Daily Price of
Various Commodities from Various Markets (Mandi)"*.

**Quirk A — User-Agent filtering.** Requests with the default
`python-requests/*` or `httpx/*` User-Agent silently time out (60 s + read
timeout, zero response bytes). Requests with `User-Agent: curl/8.7.1`
return HTTP 200 in ~0.6 s. Our client sets a curl-like UA on every request.

**Quirk B — Server-side filters are broken.** Query strings of the form
`filters[state]=Maharashtra` reliably time out even though the unfiltered
endpoint responds in ~2 s. We pull the full ~10 k-row snapshot per request
and filter client-side.

Both quirks are documented at the top of `backend/ingestion/datagovin_client.py`
so a future maintainer does not re-litigate them.

### 3. The data.gov.in resource is a snapshot, not an archive

Every returned record carries the same `arrival_date` — today. Historical
records are not retained by the API. This is a hard property of the
data source, not something we can fix in code.

Implication: the Phase 1 backfill for 18 years is impossible with this
source alone. Phase 1 ships without deep history; the panel accumulates
across days as the daily pull runs.

## What Phase 1 delivers with this fallback

Verified end-to-end on 2026-09-08:

- **10,000 raw rows** pulled from data.gov.in in 10.7 s.
- **1,178 rows** matched the four Phase-1 target commodities
  (Tomato, Onion, Potato, Banana).
- **1,172 rows** landed in `market_daily` after normalization
  (6 dropped for missing keys — expected).
- **23 states, 417 markets** auto-registered from a single snapshot.
- Reference-worthy signal: **Fatehpur APMC ₹2,587/qtl vs Varanasi APMC
  ₹1,500/qtl** for Tomato on the same day in Uttar Pradesh — a **72 %
  same-day spread** in one state. That is exactly the arbitrage-visibility
  hypothesis the capstone is built on. Phase 1 already surfaces it.

## Gate 1 impact

The formal Gate 1 test — *"Do enough mandis report ≥ 60 % of expected days?"*
— is **not yet answerable**. It presumes a multi-year panel. We have
one day. We do not fail the gate, we defer it.

**Revised Gate 1:** the pipeline runs daily for **≥ 60 days**, and at day
60 we recompute density on the accumulated panel. Every mandi that hits
≥ 60 % density in that window stays in scope for the forecaster in
Phase 3. Everything else is dropped or its state is re-scoped.

## Open workstreams for Phase 1.5

Tracked in `TODO.md` under a new "Phase 1.5 — historical + arrivals recovery":

1. **Kaggle / GitHub bulk dumps.** Multiple community repos host scraped
   AGMARKNET snapshots. Legality is grey, freshness is fixed at the last
   dump date, but for research use in a capstone this is defensible. Rank
   the top 3 dumps by recency, license, and column coverage; pick one to
   land into `market_daily` with `source='community-dump'`.
2. **Government open-data ministry inquiry.** File a data.gov.in
   dataset-request ticket asking whether the historical panel is
   publishable. Cheap to do, uncertain response time. Tanishq owns.
3. **AGMARKNET Excel downloader.** The official web dashboard exposes
   per-day Excel downloads that do not (currently) trigger the CAPTCHA.
   Scriptable, but every day is a separate download and the DOM changes
   annually. Ranked below (1) and (2) because it is fragile.
4. **Arrivals from an alternate source.** eNAM occasionally publishes
   volume alongside price for the mandis it covers (~1,000 mandis vs
   AGMARKNET's ~3,000). Worth evaluating; may partly close the
   arrivals gap for a subset of the panel.

## Defence line

This is not a hidden failure. It is a real finding, and it is now the
first chapter of the Phase 1 writeup in the thesis:

> Government open-data pipelines drift. The single largest engineering
> risk in a mandi-price project is not modelling — it is the freshness
> and durability of the source. Between the capstone kickoff and Week 2,
> AGMARKNET's REST API introduced CAPTCHA gating that silently broke every
> off-the-shelf SDK on PyPI. Our fallback path — pinning the snapshot
> endpoint, accumulating history locally, and instrumenting the pipeline
> so a source swap is a one-file change — is the reason Phase 1 still
> ships on schedule.
