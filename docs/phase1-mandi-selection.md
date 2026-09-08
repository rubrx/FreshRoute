# Phase 1 — Mandi Selection (Gate 1 Decision)

**Author:** Rubrangso
**Date:** 2026-09-08
**Related:** `docs/phase1-data-source-note.md`, `docs/data-quality-report.md`

## Decision

**Gate 1 is deferred, not failed.** The panel-density test presumes a
multi-year panel; we have one day of data because the AGMARKNET REST API
started returning `TOKEN_OR_CAPTCHA_REQUIRED` in the middle of Phase 1
(see `phase1-data-source-note.md`). We pivoted the ingestion source to
data.gov.in and now accumulate daily.

**Formal Gate 1 re-runs on 2026-11-07 (Day 60).** On that date we recompute
per-market reporting density over the accumulated window. The rule remains:
mandis reporting ≥ 60 % of days stay in scope for forecasting; others are
dropped or the state coverage is re-scoped.

## Interim scope (from the 2026-09-08 snapshot)

- **Commodities:** Tomato, Onion, Potato, Banana (unchanged).
- **States retained for the accumulation window:** all 23 states in
  today's snapshot. We deliberately do not prune yet — pruning against a
  one-day sample would delete real mandis that just did not report today.
- **Markets:** 417 auto-registered across the four commodities.

## Why we do not prune yet

Reporting density on a **1-day** window degenerates: every reporter today
is at 100 % density, every non-reporter is at 0 %. Neither number tells
us anything about the "≥ 60 % over the study window" test. Pruning on
this signal would be worse than not pruning.

The Phase 3 forecaster does not train until Week 5. There is no cost to
carrying every reporting mandi in `market_daily` until Day 60 and pruning
at that point.

## What the current snapshot does tell us

Even from one day of data we can observe the **arbitrage visibility**
premise of the project:

- Tomato in Uttar Pradesh — **Fatehpur APMC ₹2,587/qtl** vs **Varanasi
  APMC ₹1,500/qtl** on the same day, a **72 % same-day spread**.
- 23 states × 4 target commodities → 1,172 rows on the smallest possible
  time window. The panel grows daily.

That is the capstone's core claim showing up in the raw data on Day 1.

## Follow-through owners

| Item | Owner | When |
|---|---|---|
| Automate daily `pull-datagovin` (cron) | R | Week 3 |
| Re-run Gate 1 on accumulated 60-day panel | R | 2026-11-07 |
| Land at least one community historical dump into `market_daily` | R | Phase 1.5 |
| Investigate eNAM / alternate arrivals feed | M + T | Phase 1.5 |
| File data.gov.in ticket for historical publication | T | Week 3 |
