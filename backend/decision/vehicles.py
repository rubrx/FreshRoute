"""Vehicle catalogue for the recommender.

Every vehicle carries four attributes that materially change the answer
to "where should I send my tomatoes?":

- ``capacity_tonnes`` — feeds the trips×freight math.
- ``mileage_kmpl`` — feeds a **first-principles** fuel-cost line:
      fuel_litres = distance / mileage
      fuel_cost   = fuel_litres × diesel_price
  Explicit and readable in the UI, so a farmer can sanity-check it.
- ``avg_speed_kmph`` — feeds the transit-hours estimate that drives
  the spoilage integrator. A tractor at 25 km/h consumes far more of
  the shelf-life budget than a truck at 55 km/h.
- ``insulation`` — categorical multiplier on ambient temperature.
  An open tractor rides at ambient. A tarped pickup shades the load
  by a few degrees. A refrigerated truck delivers near-optimum
  storage temperature.

All numbers are seed values documented in ``notes`` — Tanishq will
replace them with quotations from live traders in Phase 7.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vehicle:
    key: str
    label: str
    capacity_tonnes: float
    mileage_kmpl: float
    avg_speed_kmph: float
    fixed_loading_rs: float
    rs_per_km_base: float          # diesel-linked ₹/km (excl. fuel line)
    diesel_price_reference_rs_per_l: float
    insulation: str                # "open" | "tarped" | "insulated" | "refrigerated"
    ambient_temp_shading_c: float  # subtracted from ambient (approximate)
    notes: str


# Reference diesel price the ₹/km base was calibrated against.
# `_km_freight_rs` scales the diesel-linked share with today's price.
_DIESEL_REFERENCE_RS_PER_L = 90.0
_DIESEL_SENSITIVITY = 0.6  # 60% of ₹/km base moves with diesel; rest is fixed overhead

VEHICLE_CATALOGUE: dict[str, Vehicle] = {
    "tractor_trolley": Vehicle(
        key="tractor_trolley",
        label="Tractor + trolley",
        capacity_tonnes=2.5,
        mileage_kmpl=6.0,
        avg_speed_kmph=25.0,
        fixed_loading_rs=500.0,
        rs_per_km_base=18.0,
        diesel_price_reference_rs_per_l=_DIESEL_REFERENCE_RS_PER_L,
        insulation="open",
        ambient_temp_shading_c=0.0,
        notes="Village-to-nearest-mandi short haul. Open trolley = full ambient exposure.",
    ),
    "pickup": Vehicle(
        key="pickup",
        label="Pickup (Chota Hathi / Tata Ace)",
        capacity_tonnes=1.0,
        mileage_kmpl=12.0,
        avg_speed_kmph=40.0,
        fixed_loading_rs=800.0,
        rs_per_km_base=22.0,
        diesel_price_reference_rs_per_l=_DIESEL_REFERENCE_RS_PER_L,
        insulation="tarped",
        ambient_temp_shading_c=2.0,
        notes="Small commercial pickup. Tarped covers reduce direct sun.",
    ),
    "truck_small": Vehicle(
        key="truck_small",
        label="14-ft truck (7 t)",
        capacity_tonnes=7.0,
        mileage_kmpl=5.0,
        avg_speed_kmph=45.0,
        fixed_loading_rs=1500.0,
        rs_per_km_base=32.0,
        diesel_price_reference_rs_per_l=_DIESEL_REFERENCE_RS_PER_L,
        insulation="tarped",
        ambient_temp_shading_c=2.0,
        notes="Common inter-district hauler. Tarped canvas roof.",
    ),
    "truck_medium": Vehicle(
        key="truck_medium",
        label="20-ft container (10 t)",
        capacity_tonnes=10.0,
        mileage_kmpl=4.0,
        avg_speed_kmph=50.0,
        fixed_loading_rs=2000.0,
        rs_per_km_base=42.0,
        diesel_price_reference_rs_per_l=_DIESEL_REFERENCE_RS_PER_L,
        insulation="tarped",
        ambient_temp_shading_c=3.0,
        notes="Standard 20-ft inter-state container. Most common long haul.",
    ),
    "reefer": Vehicle(
        key="reefer",
        label="Refrigerated truck (10 t)",
        capacity_tonnes=10.0,
        mileage_kmpl=3.2,
        avg_speed_kmph=50.0,
        fixed_loading_rs=3000.0,
        rs_per_km_base=70.0,
        diesel_price_reference_rs_per_l=_DIESEL_REFERENCE_RS_PER_L,
        insulation="refrigerated",
        ambient_temp_shading_c=20.0,
        notes="Reefer holds ~5-8C. Costs 2-3x more than open truck but saves perishables.",
    ),
}


def list_vehicles() -> list[Vehicle]:
    return list(VEHICLE_CATALOGUE.values())


def get_vehicle(key: str) -> Vehicle:
    try:
        return VEHICLE_CATALOGUE[key]
    except KeyError as exc:
        raise KeyError(f"Unknown vehicle {key!r}. Options: {list(VEHICLE_CATALOGUE)}") from exc


def transit_hours(distance_km: float, vehicle: Vehicle) -> float:
    """Assume constant average speed. Real routes involve stops; the
    Phase 4 freshness engine will refine this against OSRM durations."""
    if vehicle.avg_speed_kmph <= 0:
        raise ValueError("vehicle.avg_speed_kmph must be > 0")
    return round(distance_km / vehicle.avg_speed_kmph, 2)


def fuel_line(
    distance_km: float, vehicle: Vehicle, diesel_price_rs_per_l: float
) -> tuple[float, float]:
    """First-principles fuel line — returned as (litres, rupees).

    Kept separate from ``_km_freight_rs`` because the UI displays the
    fuel line explicitly:
        150 km ÷ 5 km/l × ₹90/l = ₹2,700
    """
    if distance_km < 0:
        raise ValueError("distance_km must be >= 0")
    if vehicle.mileage_kmpl <= 0:
        raise ValueError("vehicle.mileage_kmpl must be > 0")
    if diesel_price_rs_per_l <= 0:
        raise ValueError("diesel_price_rs_per_l must be > 0")
    litres = distance_km / vehicle.mileage_kmpl
    rupees = litres * diesel_price_rs_per_l
    return round(litres, 2), round(rupees, 2)


def other_freight_rs(
    distance_km: float,
    vehicle: Vehicle,
    quantity_tonnes: float,
    diesel_price_rs_per_l: float,
) -> float:
    """Non-fuel freight components:

    - fixed loading (per trip)
    - ₹/km base × distance × diesel_factor (driver, tolls, wear, margin)

    Diesel factor scales the diesel-linked share of the base rate:
        factor = (1 - ds) + ds × (diesel_today / diesel_ref)
    """
    if quantity_tonnes <= 0:
        raise ValueError("quantity_tonnes must be > 0")

    # ceil division without importing math.ceil, to keep dep footprint tiny
    trips = max(1, int(-(-quantity_tonnes // vehicle.capacity_tonnes)))

    diesel_factor = (1 - _DIESEL_SENSITIVITY) + _DIESEL_SENSITIVITY * (
        diesel_price_rs_per_l / vehicle.diesel_price_reference_rs_per_l
    )
    per_trip = vehicle.fixed_loading_rs + vehicle.rs_per_km_base * distance_km * diesel_factor
    return round(trips * per_trip, 2)


def trips_required(quantity_tonnes: float, vehicle: Vehicle) -> int:
    if quantity_tonnes <= 0:
        raise ValueError("quantity_tonnes must be > 0")
    return max(1, int(-(-quantity_tonnes // vehicle.capacity_tonnes)))
