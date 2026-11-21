# Shelf-life reference notes

Source: USDA **Agriculture Handbook 66** (2016 edition — *The Commercial Storage of Fruits, Vegetables, and Florist and Nursery Stocks*). Free PDF at `ars.usda.gov/ARSUserFiles/oc/np/CommercialStorage/CommercialStorage.pdf`.

The values in `data/reference/shelf_life.csv` are the ones the Q₁₀ decay integrator (`backend/freshness/decay.py`, Phase 4) will use to compute the remaining shelf-life fraction `R` along a route.

## Column semantics

| Column | Meaning | Unit |
|---|---|---|
| `commodity` | Name matching the `commodities.name` column in Postgres | — |
| `t_opt_c` | Optimal storage temperature | °C |
| `rh_opt_pct` | Optimal relative humidity (midpoint of the AH-66 recommended range) | % |
| `sl_opt_days` | Approximate storage life at `t_opt_c` and `rh_opt_pct` | days |
| `q10` | Temperature coefficient for respiration/decay | dimensionless |
| `chilling_injury_floor_c` | Below this temperature, chilling injury (pitting, black spot, off-flavour) occurs. Empty when the commodity is not chilling-sensitive | °C |
| `ethylene_sensitive` | Peel/quality damage from ambient ethylene | boolean |
| `ethylene_producer` | Produces ethylene (matters for mixed-load logistics) | boolean |
| `category` | `vegetable` \| `fruit` \| `pulse` | — |
| `notes` | Free text — cultivar caveats, storage caveats, Indian context | — |

## Range → midpoint conversion

AH-66 gives storage life as a range (e.g. "1–3 weeks" for mature-green tomato). We use the midpoint in days:

```
sl_opt_days = round((low + high) / 2 × days_per_unit)
```

Rationale: a single scalar is simpler for the Q₁₀ integrator and the range is generally symmetric. The `notes` column preserves the range in prose when it matters (e.g. cultivar-dependent).

For temperature and RH ranges the same midpoint rule applies.

## Q₁₀ assumptions

AH-66 does not tabulate Q₁₀ explicitly per commodity. It reports respiration rates at a few reference temperatures. Van't Hoff's rule gives Q₁₀ in the range 2–3 for most fresh produce over normal handling temperatures. We use:

- **Q₁₀ = 2.0** — low-respiration commodities (dry bulbs — onion, garlic; ginger)
- **Q₁₀ = 2.5** — moderate-respiration commodities (most vegetables and fruits)
- **Q₁₀ = 3.0** — high-respiration or highly perishable (banana, okra, cucumber, chilli)

This is a stylized simplification. If the field validation (Phase 7) shows the Q₁₀ = 2.5 default is off for a specific commodity, the CSV is the single place to tune it.

## Chilling injury floor

Only populated for commodities where AH-66 lists a chilling-injury threshold. Empty for commodities that tolerate near-freezing storage (onion, potato, garlic, cabbage, carrot, apple, grapes).

The Phase 4 decay engine uses this floor two ways:
1. **Hard flag** when the ambient temperature along the route drops below the floor for a commodity that is chilling-sensitive — this should be rare in Indian trucking conditions (open trucks in summer) but matters for the cold-storage stretch feature S1.
2. **Q₁₀ inversion warning** — refrigerating a tomato at 4 °C is not the "safe" thing intuition suggests. The freshness engine should surface this in the UI.

## Indian-context caveats — read before defending

1. **AH-66 assumes an unbroken cold chain.** Indian open-truck logistics routinely see 30–45 °C ambient in summer. The Q₁₀ integrator handles this correctly (higher T → faster decay), but the `sl_opt_days` value is an upper bound. Field validation in week 11 (Tanishq) will produce a **haircut factor** per commodity to apply to `sl_opt_days` for realistic transit conditions. Add a `sl_field_haircut` column to this CSV when that data lands.

2. **Cultivar variation is large.** AH-66 uses a mix of US and international cultivars. Alphonso mango behaves differently from Kesar or Totapuri. Tomato hybrids (Ansal, Vikram, Namdhari) tolerate different post-harvest handling than a US "Roma" or "Beefsteak". Where a cultivar-specific value is validated, add it as a new row `Mango — Alphonso` and match on the fuller name.

3. **Grading and pre-cooling matter more than we can model.** A tomato picked at breaker stage, field-heated to 40 °C, and loaded into an open truck has a very different decay curve from the same tomato pre-cooled to 12 °C and shipped in an insulated container. AH-66 assumes the latter. We assume the former for the base case and apply the haircut.

4. **Onion and potato dominance in Indian logistics** means we should validate their SL_opt aggressively — most consignments in the target commodities are one of these two, and getting them wrong swings the ranker heavily.

## Cross-check sources (Phase 7)

- **ICAR-CIPHET** (Central Institute of Post-Harvest Engineering and Technology, Ludhiana) — Indian post-harvest loss studies. Cited numbers on cumulative losses along the value chain by commodity.
- **NHRDF** (National Horticulture Research and Development Foundation, Nashik) — onion-specific.
- **NIPHT** (National Institute of Post-Harvest Technology).
- Direct trader interviews (Tanishq, week 11) — the definitive validation.

## When to update

Add rows or edit values only when:
1. A new commodity enters scope (edit `commodities` seed in migration 002 first).
2. Field validation produces a validated haircut or Q₁₀ correction.
3. A cultivar-specific split becomes necessary.

Every change to this CSV is a change to the freshness engine's output. Note the change in `PROGRESS.md` with the source and reasoning.
