"""Estimated in-transit spoilage.

This is a first-principles heuristic on top of the USDA AH-66 shelf-life
table (see ``data/reference/shelf_life.csv``). It is NOT a trained ML
model — Phase 4 will replace the ambient-temperature assumption with
an Open-Meteo hourly profile sampled along the OSRM polyline. Until
that lands, this module is honest about being an estimate:

    fraction_of_shelf_life_used = transit_hours / SL_at_transit_temp
    SL_at_transit_temp          = SL_opt * Q10 ^ ((T_opt - T_transit) / 10)
    spoilage_fraction           = clamp(fraction_of_shelf_life_used * dwell_factor, 0, 1)

where:
- ``dwell_factor`` (default 1.35) tacks on typical mandi-arrival dwell
  before sale, so the number reflects "how much of the produce arrives
  unsellable", not "how much is bruised on the road".
- ``T_transit`` is (ambient - vehicle.ambient_temp_shading_c),
  clipped up to the commodity's chilling-injury floor so a reefer
  doesn't get credit for freezing the produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.decision.vehicles import Vehicle

REFERENCE_DIR = Path(__file__).parent.parent.parent / "data" / "reference"
SHELF_LIFE_CSV = REFERENCE_DIR / "shelf_life.csv"

# Typical arrival-to-sale delay at mandi (unloading + auction cycle).
# Rough field estimate; refine in Phase 7 interviews.
DEFAULT_DWELL_FACTOR = 1.35

# Default assumed ambient temperature for the transit window when the
# caller doesn't specify one. Chosen as a rough India-wide daytime
# average for non-winter months. Phase 4 replaces this with Open-Meteo
# hourly along the route.
DEFAULT_AMBIENT_C = 30.0

# Any destination whose expected spoilage exceeds this fraction is
# infeasible — the produce is unlikely to arrive commercially sellable.
# 0.5 = "half the load rots" is a conservative floor for the demo.
DEFAULT_INFEASIBILITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class ShelfLifeSpec:
    commodity: str
    t_opt_c: float
    sl_opt_days: float
    q10: float
    chilling_injury_floor_c: float | None
    category: str


@dataclass(frozen=True)
class SpoilageEstimate:
    ambient_c: float
    effective_c: float
    sl_opt_days: float
    sl_at_effective_days: float
    transit_hours: float
    dwell_factor: float
    fraction_of_shelf_life_used: float
    spoilage_fraction: float          # 0..1, clamped
    feasible: bool
    reason: str                        # short human-friendly explanation


@lru_cache
def load_shelf_life() -> dict[str, ShelfLifeSpec]:
    """Return {commodity_name: ShelfLifeSpec}. Cached."""
    df = pd.read_csv(SHELF_LIFE_CSV)
    out: dict[str, ShelfLifeSpec] = {}
    for r in df.itertuples(index=False):
        floor: float | None
        raw = r.chilling_injury_floor_c
        try:
            floor = float(raw) if pd.notna(raw) else None
        except (TypeError, ValueError):
            floor = None
        out[r.commodity] = ShelfLifeSpec(
            commodity=r.commodity,
            t_opt_c=float(r.t_opt_c),
            sl_opt_days=float(r.sl_opt_days),
            q10=float(r.q10),
            chilling_injury_floor_c=floor,
            category=str(r.category),
        )
    return out


def _effective_temp_c(ambient_c: float, spec: ShelfLifeSpec, vehicle: Vehicle) -> float:
    """Vehicle insulation shades ambient down; chilling-injury floor
    prevents a reefer from freezing chilling-sensitive fruit."""
    shaded = ambient_c - vehicle.ambient_temp_shading_c
    if spec.chilling_injury_floor_c is not None:
        return max(shaded, spec.chilling_injury_floor_c)
    return shaded


def _shelf_life_days_at(
    ambient_c: float, spec: ShelfLifeSpec, vehicle: Vehicle
) -> tuple[float, float]:
    """Adjusted shelf life (days) at the effective transit temperature.

    Q10 model: rate doubles/triples for every 10 C rise; so SL shrinks
    by the same factor. ``effective_c`` returned for the UI.
    """
    effective_c = _effective_temp_c(ambient_c, spec, vehicle)
    delta = effective_c - spec.t_opt_c
    # Q10 ^ (delta / 10) is the factor by which respiration accelerates;
    # shelf-life divides by that same factor.
    factor = spec.q10 ** (delta / 10.0)
    if factor <= 0:
        # Guard against pathological inputs; ln domain protection
        factor = 1e-6
    sl_days = spec.sl_opt_days / factor
    return effective_c, max(0.01, sl_days)  # never return zero SL


def estimate_spoilage(
    commodity: str,
    transit_hours: float,
    vehicle: Vehicle,
    ambient_c: float = DEFAULT_AMBIENT_C,
    dwell_factor: float = DEFAULT_DWELL_FACTOR,
    infeasibility_threshold: float = DEFAULT_INFEASIBILITY_THRESHOLD,
) -> SpoilageEstimate | None:
    """Compute the expected spoilage fraction for a delivery.

    Returns ``None`` when the commodity is not in the shelf-life table;
    the caller should skip that mandi with a clear "no shelf-life data"
    reason rather than pretend zero spoilage.
    """
    spec = load_shelf_life().get(commodity)
    if spec is None:
        return None
    if transit_hours < 0:
        raise ValueError("transit_hours must be >= 0")

    effective_c, sl_days = _shelf_life_days_at(ambient_c, spec, vehicle)
    sl_hours = sl_days * 24.0

    fraction_used = (transit_hours * dwell_factor) / sl_hours
    spoilage = max(0.0, min(1.0, fraction_used))

    feasible = spoilage < infeasibility_threshold

    if not feasible:
        reason = (
            f"~{spoilage*100:.0f}% expected spoilage — the {vehicle.label.lower()} "
            f"cannot keep {commodity.lower()} sellable over ~{transit_hours:.1f} h "
            f"at {effective_c:.0f}°C."
        )
    elif spoilage >= 0.25:
        reason = (
            f"Tight but feasible — ~{spoilage*100:.0f}% expected loss. "
            f"Consider a cooler vehicle or shorter route."
        )
    else:
        reason = (
            f"Comfortable margin — ~{spoilage*100:.0f}% expected loss "
            f"over {transit_hours:.1f} h at {effective_c:.0f}°C."
        )

    return SpoilageEstimate(
        ambient_c=ambient_c,
        effective_c=round(effective_c, 1),
        sl_opt_days=spec.sl_opt_days,
        sl_at_effective_days=round(sl_days, 2),
        transit_hours=transit_hours,
        dwell_factor=dwell_factor,
        fraction_of_shelf_life_used=round(fraction_used, 3),
        spoilage_fraction=round(spoilage, 3),
        feasible=feasible,
        reason=reason,
    )
