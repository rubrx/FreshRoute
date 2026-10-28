# data/reference — versioned lookup tables

These files are checked into the repo. They change rarely and only with a deliberate commit. Do **not** gitignore them.

| File | Rows | Source | Purpose |
|------|------|--------|---------|
| `shelf_life.csv` | 16 commodities | USDA AH-66 (transcribed) | Shelf life at optimal °C + Q₁₀ factor for each commodity. Used by the freshness engine to compute remaining life along the route temperature profile. |
| `costs.csv` | 10 states | State APMC rules (manually sourced) | APMC commission %, development cess %, entry fee, labour, and weighment rates per state. Used by the cost model to compute net ₹/tonne. |
| `freight.csv` | 5 rows | Internal seed values | Fuel efficiency and load factors per vehicle type (mini-truck, tata-407, truck-10t). Used by the cost model to estimate diesel cost. |
| `district_centroids.csv` | ~150 districts | Nominatim + Agmarknet geocoding | Lat/lon centroid per (state, district) pair. Used by the `/geo/districts` endpoint as a GPS-fallback picker when the farmer cannot share location. |
| `state_centroids.csv` | 37 states/UTs | Same as above | Lat/lon centroid per state. Used as a coarser fallback when no district match is found. |

## Updating a file

1. Edit the CSV locally and verify columns/types match existing schema.
2. Restart the API — the `@lru_cache` loaders in `geo.py` and `costs.py` re-read on startup.
3. Commit with a message like `data: update costs.csv — Karnataka cess rate revised`.

## Schema notes

**`shelf_life.csv`** — columns: `commodity, sl_opt_days, t_opt_c, q10`  
**`costs.csv`** — columns: `state, apmc_commission_pct, cess_pct, entry_fee_rs_per_tonne, labour_rs_per_tonne, weighment_rs_per_tonne, notes`  
**`freight.csv`** — columns: `vehicle_key, label, truck_size_tonnes, fuel_efficiency_km_per_l, load_factor`  
**`district_centroids.csv`** — columns: `state, district, lat, lon`  
**`state_centroids.csv`** — columns: `state, lat, lon`
