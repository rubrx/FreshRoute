"""End-to-end mandi recommender.

Answers one question:

    "I have <quantity> tonnes of <commodity> to sell.
     Where and when should I send them so I make the most money
     without the produce becoming unsellable?"

Given (origin lat/lon, commodity, quantity, vehicle, diesel price):

1. Pull the latest reported modal price at every mandi trading this
   commodity today.
2. Resolve each mandi to a district-centroid lat/lon (or state
   centroid as fallback, tagged as an approximation).
3. Compute great-circle × road-detour distance; drop anything outside
   the search radius (default 250 km).
4. Estimate transit hours from the vehicle's average speed, expected
   fuel litres + rupees from mileage, and other freight components
   from the seed rate table.
5. Estimate spoilage from the shelf-life table using a Q10 model at
   the effective transit temperature (ambient - vehicle shading).
6. Apply the mandi's APMC / cess / entry-fee / labour / weighment
   deductions from ``data/reference/costs.csv``.
7. Rank by **expected net realization per tonne**:
       gross    = quote × quantity × (1 - spoilage)
       net      = gross - fuel - other_freight - APMC - cess - entry
                       - labour - weighment
       per_t    = net / quantity
8. Drop any destination whose spoilage exceeds a feasibility floor;
   surface the reason so the UI can explain why it was excluded.

No forecasting yet — Phase 3 will replace ``quote`` with a P50
price forecast for the arrival day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.analysis.market_intelligence import build_market_context_map
from backend.cost.model import QUINTALS_PER_TONNE, load_state_costs
from backend.decision.geo import Centroid, estimated_road_km, resolve_centroid
from backend.decision.spoilage import (
    DEFAULT_AMBIENT_C,
    DEFAULT_INFEASIBILITY_THRESHOLD,
    SpoilageEstimate,
    estimate_spoilage,
)
from backend.decision.vehicles import (
    Vehicle,
    fuel_line,
    other_freight_rs,
    transit_hours,
    trips_required,
)

# Anything below this ₹/qtl is treated as a data-quality artefact
# (variety mislabelling, unit typo). Same floor the arbitrage endpoint uses.
PRICE_FLOOR_RS_PER_QUINTAL = 100.0

DEFAULT_RADIUS_KM = 250.0
DEFAULT_MAX_RESULTS = 8


@dataclass(frozen=True)
class CostBreakdown:
    fuel_litres: float
    fuel_rs: float
    other_freight_rs: float
    apmc_commission_rs: float
    cess_rs: float
    entry_fee_rs: float
    labour_rs: float
    weighment_rs: float
    total_deductions_rs: float


@dataclass(frozen=True)
class Recommendation:
    rank: int
    market_id: int
    market_name: str
    district: str
    state: str

    distance_km: float
    distance_source: str        # "district" | "state" (state = approximate)

    transit_hours: float
    trips: int

    modal_price_rs_per_quintal: float
    quantity_tonnes: float
    gross_revenue_rs: float
    expected_saleable_revenue_rs: float   # gross × (1 - spoilage)

    costs: CostBreakdown

    net_revenue_rs: float
    net_rs_per_tonne: float

    spoilage: SpoilageEstimate

    price_status: str            # "live" — echoed for UI truth-labelling
    price_snapshot_date: date
    why: str                     # short recommendation summary

    # Price context relative to peers
    price_pct_rank_in_state: float = 50.0   # 0=cheapest, 100=priciest in state
    vs_state_median_rs_per_qtl: float = 0.0
    vs_national_median_rs_per_qtl: float = 0.0


@dataclass(frozen=True)
class InfeasibleCandidate:
    market_name: str
    district: str
    state: str
    distance_km: float
    reason: str


@dataclass(frozen=True)
class RecommendationResult:
    origin_lat: float
    origin_lon: float
    radius_km: float
    commodity: str
    quantity_tonnes: float
    vehicle_key: str
    diesel_price_rs_per_l: float
    ambient_c: float
    snapshot_date: date | None

    considered: int              # mandis inside the radius
    ranked: list[Recommendation]
    infeasible: list[InfeasibleCandidate]

    caveats: list[str]           # data-truth disclosures for the UI


def _load_candidates(db: Session, commodity: str) -> list[dict]:
    """Latest-day modal price for every mandi selling this commodity."""
    latest = db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()
    if latest is None:
        return []

    sql = text(
        """
        SELECT md.market_id,
               m.name    AS market_name,
               m.district,
               s.name    AS state,
               md.modal_price,
               md.date   AS snapshot_date
          FROM market_daily md
          JOIN commodities c ON c.id = md.commodity_id
          JOIN markets     m ON m.id = md.market_id
          JOIN states      s ON s.id = m.state_id
         WHERE md.date = :d
           AND c.name = :commodity
           AND md.modal_price IS NOT NULL
           AND md.modal_price >= :floor
         ORDER BY md.modal_price DESC
        """
    )
    rows = db.execute(
        sql,
        {"d": latest, "commodity": commodity, "floor": PRICE_FLOOR_RS_PER_QUINTAL},
    ).mappings().all()
    return [dict(r) for r in rows]


def _price_status_caveat(snapshot_date: date | None) -> list[str]:
    caveats: list[str] = []
    if snapshot_date:
        caveats.append(
            f"Mandi prices are the latest available data.gov.in snapshot ({snapshot_date}). "
            "Live intra-day quotes are not yet wired in."
        )
    caveats.append(
        "Distances are haversine × 1.30 road-detour estimate; road distance via OSRM "
        "will replace this in Phase 2."
    )
    caveats.append(
        "Spoilage uses a Q10 shelf-life model at an assumed ambient temperature. "
        "Route-sampled weather (Open-Meteo) is a Phase 4 upgrade."
    )
    caveats.append(
        "Freight and mandi charges (APMC, cess, entry fee, labour, weighment) are "
        "seed values from data/reference/*.csv, not per-mandi live quotes."
    )
    return caveats


def recommend(
    db: Session,
    origin_lat: float,
    origin_lon: float,
    commodity: str,
    quantity_tonnes: float,
    vehicle: Vehicle,
    diesel_price_rs_per_l: float,
    ambient_c: float = DEFAULT_AMBIENT_C,
    radius_km: float = DEFAULT_RADIUS_KM,
    max_results: int = DEFAULT_MAX_RESULTS,
    infeasibility_threshold: float = DEFAULT_INFEASIBILITY_THRESHOLD,
) -> RecommendationResult:
    """Main entry — see module docstring."""
    if quantity_tonnes <= 0:
        raise ValueError("quantity_tonnes must be > 0")
    if radius_km <= 0:
        raise ValueError("radius_km must be > 0")
    if not -90 <= origin_lat <= 90 or not -180 <= origin_lon <= 180:
        raise ValueError("origin_lat/origin_lon out of range")

    state_costs = load_state_costs()
    raw = _load_candidates(db, commodity)

    snapshot_date: date | None = raw[0]["snapshot_date"] if raw else None

    # Price context map: market_id → percentile rank + vs-median signals.
    # Built once, O(N) over the snapshot — cheap relative to the loop.
    context_map = build_market_context_map(db, commodity)

    considered = 0
    ranked: list[Recommendation] = []
    infeasible: list[InfeasibleCandidate] = []

    for row in raw:
        centroid: Centroid | None = resolve_centroid(row["state"], row["district"])
        if centroid is None:
            # Silently skip mandis we cannot place on the map. Alternative:
            # surface them as infeasible with reason "no coordinates". The
            # current district+state coverage catches most volume; will
            # revisit once real geocoding runs.
            continue

        distance = estimated_road_km(
            origin_lat, origin_lon, centroid.latitude, centroid.longitude
        )
        if distance > radius_km:
            continue

        considered += 1

        # Cost rates keyed on state (seed table); skip if we don't have rates.
        rates = state_costs.get(row["state"])
        if rates is None:
            infeasible.append(
                InfeasibleCandidate(
                    market_name=row["market_name"],
                    district=row["district"] or "",
                    state=row["state"],
                    distance_km=distance,
                    reason=f"No cost rates seeded for {row['state']} — cannot price this mandi.",
                )
            )
            continue

        hours = transit_hours(distance, vehicle)
        spoilage = estimate_spoilage(
            commodity=commodity,
            transit_hours=hours,
            vehicle=vehicle,
            ambient_c=ambient_c,
        )
        if spoilage is None:
            infeasible.append(
                InfeasibleCandidate(
                    market_name=row["market_name"],
                    district=row["district"] or "",
                    state=row["state"],
                    distance_km=distance,
                    reason=f"No shelf-life data for {commodity} — cannot judge spoilage.",
                )
            )
            continue

        if not spoilage.feasible:
            infeasible.append(
                InfeasibleCandidate(
                    market_name=row["market_name"],
                    district=row["district"] or "",
                    state=row["state"],
                    distance_km=distance,
                    reason=spoilage.reason,
                )
            )
            continue

        modal_rs_qtl = float(row["modal_price"])
        gross = modal_rs_qtl * QUINTALS_PER_TONNE * quantity_tonnes
        saleable = gross * (1.0 - spoilage.spoilage_fraction)

        litres, fuel_rs = fuel_line(distance, vehicle, diesel_price_rs_per_l)
        other_frt = other_freight_rs(distance, vehicle, quantity_tonnes, diesel_price_rs_per_l)
        apmc = gross * rates.apmc_commission_pct / 100.0
        cess = gross * rates.cess_pct / 100.0
        entry_fee = rates.entry_fee_rs_per_tonne * quantity_tonnes
        labour = rates.labour_rs_per_tonne * quantity_tonnes
        weighment = rates.weighment_rs_per_tonne * quantity_tonnes

        total_ded = fuel_rs + other_frt + apmc + cess + entry_fee + labour + weighment
        net = saleable - total_ded

        breakdown = CostBreakdown(
            fuel_litres=litres,
            fuel_rs=round(fuel_rs, 2),
            other_freight_rs=round(other_frt, 2),
            apmc_commission_rs=round(apmc, 2),
            cess_rs=round(cess, 2),
            entry_fee_rs=round(entry_fee, 2),
            labour_rs=round(labour, 2),
            weighment_rs=round(weighment, 2),
            total_deductions_rs=round(total_ded, 2),
        )

        ctx = context_map.get(int(row["market_id"]))
        rank_label = ""
        if ctx:
            pct = ctx.price_pct_rank_in_state
            if pct >= 90:
                rank_label = f" Top-{int(100 - pct) + 1}% price in {row['state']}."
            elif pct >= 75:
                rank_label = f" Upper-quartile price in {row['state']}."
        why = (
            f"₹{net / quantity_tonnes:,.0f}/tonne net after {spoilage.spoilage_fraction*100:.0f}% "
            f"expected spoilage and freight over {distance:.0f} km.{rank_label}"
        )

        ranked.append(
            Recommendation(
                rank=0,  # filled after sort
                market_id=int(row["market_id"]),
                market_name=row["market_name"],
                district=row["district"] or "",
                state=row["state"],
                distance_km=round(distance, 1),
                distance_source=centroid.source,
                transit_hours=hours,
                trips=trips_required(quantity_tonnes, vehicle),
                modal_price_rs_per_quintal=modal_rs_qtl,
                quantity_tonnes=quantity_tonnes,
                gross_revenue_rs=round(gross, 2),
                expected_saleable_revenue_rs=round(saleable, 2),
                costs=breakdown,
                net_revenue_rs=round(net, 2),
                net_rs_per_tonne=round(net / quantity_tonnes, 2),
                spoilage=spoilage,
                price_status="live",
                price_snapshot_date=row["snapshot_date"],
                why=why,
                price_pct_rank_in_state=ctx.price_pct_rank_in_state if ctx else 50.0,
                vs_state_median_rs_per_qtl=ctx.vs_state_median_rs_per_qtl if ctx else 0.0,
                vs_national_median_rs_per_qtl=ctx.vs_national_median_rs_per_qtl if ctx else 0.0,
            )
        )

    ranked.sort(key=lambda r: r.net_rs_per_tonne, reverse=True)
    ranked = [
        Recommendation(**{**r.__dict__, "rank": i + 1})
        for i, r in enumerate(ranked[:max_results])
    ]

    return RecommendationResult(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        radius_km=radius_km,
        commodity=commodity,
        quantity_tonnes=quantity_tonnes,
        vehicle_key=vehicle.key,
        diesel_price_rs_per_l=diesel_price_rs_per_l,
        ambient_c=ambient_c,
        snapshot_date=snapshot_date,
        considered=considered,
        ranked=ranked,
        infeasible=sorted(infeasible, key=lambda x: x.distance_km)[:max_results],
        caveats=_price_status_caveat(snapshot_date),
    )
