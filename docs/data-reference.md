# Reference data

All files live in `data/reference/` and are checked into the repo. They change rarely and only with a deliberate commit.

| File | Rows | Source | Purpose |
|---|---|---|---|
| `shelf_life.csv` | 16 commodities | USDA AH-66 (transcribed) | Shelf life at optimal °C + Q₁₀ factor. Used by the freshness engine to compute remaining life along the route temperature profile. |
| `costs.csv` | ~10 states | State APMC rules (manually sourced) | APMC commission %, development cess %, entry fee, labour, and weighment rates per state. Used by the cost model to compute net ₹/tonne. |
| `freight.csv` | 5 truck sizes | Seed values | ₹/km base rate, reference diesel price, and fixed loading charge per truck size. Used by the cost calculator (`cost/model.py`). The diesel sensitivity (60%) is a constant in code, not a column. Tanishq updates from live trader quotes in Phase 7. |
| `district_centroids.csv` | ~150 districts | Nominatim + Agmarknet geocoding | Lat/lon centroid per (state, district). Used by `/geo/districts` as a GPS-fallback location picker. |
| `state_centroids.csv` | ~37 states/UTs | Same | Coarser fallback when no district match is found. |

> The recommender (`backend/decision/`) takes its vehicle and freight parameters from `backend/decision/vehicles.py`, not from `freight.csv`. The two tables are maintained separately and should be kept consistent.

## Column schemas

**`shelf_life.csv`**
`commodity, t_opt_c, rh_opt_pct, sl_opt_days, q10, chilling_injury_floor_c, ethylene_sensitive, ethylene_producer, category, notes`

**`costs.csv`**
`state, apmc_commission_pct, cess_pct, entry_fee_rs_per_tonne, labour_rs_per_tonne, weighment_rs_per_tonne, notes`

**`freight.csv`**
`truck_size_tonnes, rs_per_km_base, diesel_price_reference_rs_per_l, fixed_loading_rs, notes`

**`district_centroids.csv`** / **`state_centroids.csv`**
`state, district, latitude, longitude` / `state, latitude, longitude, notes`

## Updating a file

1. Edit the CSV and verify columns/types match the schema above.
2. Restart the API — the `@lru_cache` loaders in `decision/geo.py`, `decision/spoilage.py` and `cost/model.py` re-read on startup.
3. Commit: `data: update costs.csv — Karnataka cess rate revised`.

For shelf-life changes see [`docs/shelf-life.md`](shelf-life.md) — every edit has freshness engine implications.
