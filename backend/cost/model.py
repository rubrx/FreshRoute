"""Cost model v1 — the ranker's objective function.

Turns a mandi quote (₹/quintal) into an itemized net realization (₹/tonne)
after freight, APMC commission, cess, entry fee, labour, and weighment.

All figures are seed values (see `data/reference/costs.csv` and
`data/reference/freight.csv`) — Tanishq refines them in Phase 7 field
interviews. The model itself never changes; only the reference CSVs do.

Units are explicit in every field name to prevent the ₹/quintal ↔ ₹/tonne
confusion that will otherwise silently corrupt the ranker.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

REFERENCE_DIR = Path(__file__).parent.parent.parent / "data" / "reference"
COSTS_CSV = REFERENCE_DIR / "costs.csv"
FREIGHT_CSV = REFERENCE_DIR / "freight.csv"

# Agmarknet quotes ₹/quintal; the ranker works in ₹/tonne.
QUINTALS_PER_TONNE = 10.0

# Reference diesel price for the freight table. When the actual diesel price
# differs, freight scales linearly (diesel is the dominant variable cost).
_DIESEL_SENSITIVITY = 0.6  # 60% of ₹/km cost varies with diesel; rest is fixed.


@dataclass(frozen=True)
class StateCostRates:
    state: str
    apmc_commission_pct: float
    cess_pct: float
    entry_fee_rs_per_tonne: float
    labour_rs_per_tonne: float
    weighment_rs_per_tonne: float


@dataclass(frozen=True)
class FreightSpec:
    truck_size_tonnes: float
    rs_per_km_base: float
    diesel_price_reference_rs_per_l: float
    fixed_loading_rs: float


@dataclass(frozen=True)
class CostBreakdown:
    """Every line item is in ₹, at the whole-consignment level unless suffixed.

    Sum of the deductions equals `gross_revenue - net_revenue`. Divide any
    field by `quantity_tonnes` for per-tonne figures.
    """
    # Inputs echoed back for the UI
    quote_price_rs_per_quintal: float
    quantity_tonnes: float
    distance_km: float
    truck_size_tonnes: float
    dest_state: str
    diesel_price_rs_per_l: float

    # Revenue
    gross_revenue_rs: float          # quote × quantity

    # Deductions
    freight_rs: float                # ₹/km × km, scaled to diesel today
    apmc_commission_rs: float        # % of gross
    cess_rs: float                   # % of gross
    entry_fee_rs: float              # ₹/tonne × quantity
    labour_rs: float                 # ₹/tonne × quantity  (loading + unloading)
    weighment_rs: float              # ₹/tonne × quantity

    # Result
    total_deductions_rs: float
    net_revenue_rs: float
    net_rs_per_tonne: float


@lru_cache
def load_state_costs() -> dict[str, StateCostRates]:
    """Return {state_name: StateCostRates}. Cached because the CSV is small
    and read-mostly."""
    df = pd.read_csv(COSTS_CSV)
    out: dict[str, StateCostRates] = {}
    for row in df.itertuples(index=False):
        out[row.state] = StateCostRates(
            state=row.state,
            apmc_commission_pct=float(row.apmc_commission_pct),
            cess_pct=float(row.cess_pct),
            entry_fee_rs_per_tonne=float(row.entry_fee_rs_per_tonne),
            labour_rs_per_tonne=float(row.labour_rs_per_tonne),
            weighment_rs_per_tonne=float(row.weighment_rs_per_tonne),
        )
    return out


@lru_cache
def load_freight_table() -> list[FreightSpec]:
    """Return freight specs sorted by truck size ascending."""
    df = pd.read_csv(FREIGHT_CSV).sort_values("truck_size_tonnes")
    return [
        FreightSpec(
            truck_size_tonnes=float(row.truck_size_tonnes),
            rs_per_km_base=float(row.rs_per_km_base),
            diesel_price_reference_rs_per_l=float(row.diesel_price_reference_rs_per_l),
            fixed_loading_rs=float(row.fixed_loading_rs),
        )
        for row in df.itertuples(index=False)
    ]


def pick_truck(quantity_tonnes: float) -> FreightSpec:
    """Choose the smallest truck that fits the load. Falls back to the largest
    when the load exceeds any single truck (multi-truck cost = size × trips)."""
    if quantity_tonnes <= 0:
        raise ValueError("quantity_tonnes must be > 0")

    table = load_freight_table()
    for spec in table:
        if spec.truck_size_tonnes >= quantity_tonnes:
            return spec
    # Load larger than any single truck. Return the biggest; caller decides
    # whether to charge for multiple trips.
    return table[-1]


def _freight_cost_rs(
    spec: FreightSpec,
    distance_km: float,
    quantity_tonnes: float,
    diesel_price_rs_per_l: float,
) -> float:
    """One-way freight. Scales the diesel-linked component with today's diesel.

    freight = fixed_loading + (rs_per_km_base × distance) × diesel_factor
    diesel_factor = (1 − ds) + ds × (diesel_today / diesel_ref)

    where ds is `_DIESEL_SENSITIVITY`.
    """
    if distance_km < 0:
        raise ValueError("distance_km must be >= 0")

    trips = max(1, -(-quantity_tonnes // spec.truck_size_tonnes))  # ceil division

    diesel_factor = (1 - _DIESEL_SENSITIVITY) + _DIESEL_SENSITIVITY * (
        diesel_price_rs_per_l / spec.diesel_price_reference_rs_per_l
    )
    per_trip = spec.fixed_loading_rs + spec.rs_per_km_base * distance_km * diesel_factor
    return trips * per_trip


def net_realization(
    quote_price_rs_per_quintal: float,
    quantity_tonnes: float,
    distance_km: float,
    dest_state: str,
    diesel_price_rs_per_l: float,
    truck: FreightSpec | None = None,
) -> CostBreakdown:
    """Pure function. Given a quote at a destination mandi and route info,
    returns the itemized net realization.

    - `quote_price_rs_per_quintal` — modal/forecast price at destination
    - `quantity_tonnes` — consignment size
    - `distance_km` — road distance to destination (from OSRM in Phase 2)
    - `dest_state` — state key into `costs.csv`
    - `diesel_price_rs_per_l` — today's diesel (freight scales with this)
    - `truck` — optional override; otherwise picked by `pick_truck`
    """
    if quantity_tonnes <= 0:
        raise ValueError("quantity_tonnes must be > 0")
    if quote_price_rs_per_quintal < 0:
        raise ValueError("quote_price must be >= 0")

    state_rates = load_state_costs().get(dest_state)
    if state_rates is None:
        raise KeyError(
            f"No cost rates for state {dest_state!r}. "
            f"Add a row to data/reference/costs.csv."
        )

    truck = truck or pick_truck(quantity_tonnes)

    gross_revenue = (
        quote_price_rs_per_quintal * QUINTALS_PER_TONNE * quantity_tonnes
    )

    freight = _freight_cost_rs(truck, distance_km, quantity_tonnes, diesel_price_rs_per_l)
    apmc = gross_revenue * (state_rates.apmc_commission_pct / 100.0)
    cess = gross_revenue * (state_rates.cess_pct / 100.0)
    entry_fee = state_rates.entry_fee_rs_per_tonne * quantity_tonnes
    labour = state_rates.labour_rs_per_tonne * quantity_tonnes
    weighment = state_rates.weighment_rs_per_tonne * quantity_tonnes

    total_deductions = freight + apmc + cess + entry_fee + labour + weighment
    net = gross_revenue - total_deductions

    return CostBreakdown(
        quote_price_rs_per_quintal=quote_price_rs_per_quintal,
        quantity_tonnes=quantity_tonnes,
        distance_km=distance_km,
        truck_size_tonnes=truck.truck_size_tonnes,
        dest_state=dest_state,
        diesel_price_rs_per_l=diesel_price_rs_per_l,
        gross_revenue_rs=round(gross_revenue, 2),
        freight_rs=round(freight, 2),
        apmc_commission_rs=round(apmc, 2),
        cess_rs=round(cess, 2),
        entry_fee_rs=round(entry_fee, 2),
        labour_rs=round(labour, 2),
        weighment_rs=round(weighment, 2),
        total_deductions_rs=round(total_deductions, 2),
        net_revenue_rs=round(net, 2),
        net_rs_per_tonne=round(net / quantity_tonnes, 2),
    )
