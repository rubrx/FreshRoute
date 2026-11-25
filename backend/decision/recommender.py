"""Ranks mandis by expected net ₹/tonne after spoilage, freight, and mandi charges.

Revenue is priced from the P50 forecast for the arrival day (1-3 days ahead, set by transit
time) when the forecaster has enough recent history for that mandi; otherwise from today's
quote. The forecast's P10/P90 are carried through as a net-revenue range.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import structlog
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
from backend.forecasting.serve import (
    MarketForecast,
    PriceForecaster,
    get_forecaster,
    horizon_days_for_hours,
)

log = structlog.get_logger(__name__)

# Anything below this ₹/qtl is treated as a data-quality artefact
# (variety mislabelling, unit typo). Same floor the arbitrage endpoint uses.
PRICE_FLOOR_RS_PER_QUINTAL = 100.0

DEFAULT_RADIUS_KM = 250.0
DEFAULT_MAX_RESULTS = 8

# How far back to look when deciding which day's snapshot is the latest complete one.
SNAPSHOT_LOOKBACK_DAYS = 14


def price_outcome(
    price_rs_qtl: float,
    quantity_tonnes: float,
    spoilage_fraction: float,
    apmc_pct: float,
    cess_pct: float,
    fixed_rs: float,
) -> tuple[float, float, float, float, float]:
    """Revenue and net if the load sells at ``price_rs_qtl``.

    Returns ``(gross, saleable, apmc, cess, net)``. APMC commission and cess are percentages
    of gross; ``fixed_rs`` is everything that does not depend on the price (fuel, other
    freight, entry fee, labour, weighment).
    """
    gross = price_rs_qtl * QUINTALS_PER_TONNE * quantity_tonnes
    saleable = gross * (1.0 - spoilage_fraction)
    apmc = gross * apmc_pct / 100.0
    cess = gross * cess_pct / 100.0
    return gross, saleable, apmc, cess, saleable - fixed_rs - apmc - cess


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

    # Forecast. `modal_price_rs_per_quintal` above stays TODAY'S quote; the price that
    # revenue is computed from is `expected_price_rs_per_quintal`.
    expected_price_rs_per_quintal: float = 0.0
    price_basis: str = "snapshot"             # "forecast" | "snapshot"
    forecast_horizon_days: int | None = None
    forecast_p10_rs_per_quintal: float | None = None
    forecast_p90_rs_per_quintal: float | None = None
    net_rs_per_tonne_p10: float | None = None  # net if the price lands at the forecast P10
    net_rs_per_tonne_p90: float | None = None


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

    considered: int
    ranked: list[Recommendation]
    infeasible: list[InfeasibleCandidate]
    nearest_mandi: Recommendation | None  # closest by distance among ranked[]

    caveats: list[str]

    forecast_used: bool = False           # at least one ranked mandi is priced from a forecast
    forecast_model_trained_through: str | None = None


def choose_snapshot(counts: list[tuple[date, int]], min_completeness: float = 0.5) -> date | None:
    """Latest day whose snapshot looks complete, from ``(date, mandis_reporting)`` pairs.

    The daily feed fills during the day, so a pull made early leaves a thin partial snapshot
    (e.g. 93 rows when a normal day has 16,000). Ranking a handful of mandis as if they were
    the whole market would be wrong, so a day only counts if at least ``min_completeness`` of
    the best recent day's mandis reported.
    """
    if not counts:
        return None
    best = max(n for _, n in counts)
    complete = [d for d, n in counts if n >= min_completeness * best]
    return max(complete) if complete else max(d for d, _ in counts)


def _pick_snapshot_date(db: Session, commodity: str) -> date | None:
    rows = db.execute(
        text(
            """
            SELECT md.date AS d, COUNT(DISTINCT md.market_id) AS n
              FROM market_daily md
              JOIN commodities c ON c.id = md.commodity_id
             WHERE c.name = :commodity
               AND md.modal_price IS NOT NULL
               AND md.date >= (SELECT MAX(date) FROM market_daily) - CAST(:days AS integer)
             GROUP BY md.date
            """
        ),
        {"commodity": commodity, "days": SNAPSHOT_LOOKBACK_DAYS},
    ).all()
    picked = choose_snapshot([(r.d, int(r.n)) for r in rows])
    if picked is not None:
        return picked
    # nothing in the recent window: fall back to the latest date this commodity has at all
    return db.execute(
        text(
            "SELECT MAX(md.date) FROM market_daily md "
            "JOIN commodities c ON c.id = md.commodity_id WHERE c.name = :commodity"
        ),
        {"commodity": commodity},
    ).scalar()


def _load_candidates(db: Session, commodity: str) -> list[dict]:
    """Latest complete-day modal price for every mandi selling this commodity."""
    latest = _pick_snapshot_date(db, commodity)
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
            f"Prices are the latest data.gov.in snapshot ({snapshot_date}). "
            "Intra-day live quotes are not available."
        )
    caveats.append(
        "Distances are haversine × 1.30 road-detour estimate, not actual road distance."
    )
    caveats.append(
        "Spoilage uses a Q10 shelf-life model at the stated ambient temperature."
    )
    caveats.append(
        "Freight and mandi charges are reference-table estimates, not per-mandi live quotes."
    )
    return caveats


def pick_nearest(ranked: list[Recommendation]) -> Recommendation | None:
    """Closest mandi by distance among the feasible, ranked results.

    This is the naive baseline ("just go to the nearest mandi") that the UI
    compares the #1 pick against.
    """
    return min(ranked, key=lambda r: r.distance_km) if ranked else None


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
    use_forecast: bool = True,
    forecaster: PriceForecaster | None = None,
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

    # Forecasts for the arrival day. Any failure (no model, no history, a bug) falls back
    # to today's quote: forecasting must never break the recommendation itself.
    forecasts: dict[tuple[int, int], MarketForecast] = {}
    fc_engine: PriceForecaster | None = None
    if use_forecast and snapshot_date is not None:
        fc_engine = forecaster or get_forecaster()
        if fc_engine is not None:
            try:
                forecasts = fc_engine.forecast(db, commodity, snapshot_date)
            except Exception:  # noqa: BLE001
                log.exception("forecast_failed_using_snapshot_prices", commodity=commodity)
                forecasts = {}

    context_map = build_market_context_map(db, commodity)

    considered = 0
    ranked: list[Recommendation] = []
    infeasible: list[InfeasibleCandidate] = []

    for row in raw:
        centroid: Centroid | None = resolve_centroid(row["state"], row["district"])
        if centroid is None:
            continue  # no coordinates — skip silently; coverage handles most volume

        distance = estimated_road_km(
            origin_lat, origin_lon, centroid.latitude, centroid.longitude
        )
        if distance > radius_km:
            continue

        considered += 1

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

        modal_rs_qtl = float(row["modal_price"])      # today's quote (snapshot)

        # The price we expect to realise: the forecast for the arrival day when there is
        # one (P50, with P10/P90 as the range), otherwise today's quote.
        fc = forecasts.get((int(row["market_id"]), horizon_days_for_hours(hours)))
        expected_rs_qtl = fc.p50 if fc else modal_rs_qtl

        # fuel_line() is one leg for one trip; a load bigger than the vehicle
        # needs several trips, so fuel scales with trips just like other freight.
        trips = trips_required(quantity_tonnes, vehicle)
        litres_per_trip, fuel_per_trip = fuel_line(distance, vehicle, diesel_price_rs_per_l)
        litres = round(litres_per_trip * trips, 2)
        fuel_rs = round(fuel_per_trip * trips, 2)
        other_frt = other_freight_rs(distance, vehicle, quantity_tonnes, diesel_price_rs_per_l)
        entry_fee = rates.entry_fee_rs_per_tonne * quantity_tonnes
        labour = rates.labour_rs_per_tonne * quantity_tonnes
        weighment = rates.weighment_rs_per_tonne * quantity_tonnes

        fixed = fuel_rs + other_frt + entry_fee + labour + weighment
        spoil = spoilage.spoilage_fraction
        gross, saleable, apmc, cess, net = price_outcome(
            expected_rs_qtl, quantity_tonnes, spoil,
            rates.apmc_commission_pct, rates.cess_pct, fixed,
        )
        total_ded = fixed + apmc + cess

        net_p10 = net_p90 = None
        if fc:
            net_p10 = price_outcome(
                fc.p10, quantity_tonnes, spoil, rates.apmc_commission_pct, rates.cess_pct, fixed
            )[-1] / quantity_tonnes
            net_p90 = price_outcome(
                fc.p90, quantity_tonnes, spoil, rates.apmc_commission_pct, rates.cess_pct, fixed
            )[-1] / quantity_tonnes

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
        forecast_note = ""
        if fc:
            forecast_note = (
                f" Expected price ₹{fc.p50:,.0f}/qtl on arrival "
                f"(likely range ₹{fc.p10:,.0f}–₹{fc.p90:,.0f})."
            )
        why = (
            f"₹{net / quantity_tonnes:,.0f}/tonne net after {spoilage.spoilage_fraction*100:.0f}% "
            f"expected spoilage and freight over {distance:.0f} km.{forecast_note}{rank_label}"
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
                trips=trips,
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
                expected_price_rs_per_quintal=round(expected_rs_qtl, 2),
                price_basis="forecast" if fc else "snapshot",
                forecast_horizon_days=fc.horizon_days if fc else None,
                forecast_p10_rs_per_quintal=round(fc.p10, 2) if fc else None,
                forecast_p90_rs_per_quintal=round(fc.p90, 2) if fc else None,
                net_rs_per_tonne_p10=round(net_p10, 2) if net_p10 is not None else None,
                net_rs_per_tonne_p90=round(net_p90, 2) if net_p90 is not None else None,
            )
        )

    ranked.sort(key=lambda r: r.net_rs_per_tonne, reverse=True)
    ranked = [
        Recommendation(**{**r.__dict__, "rank": i + 1})
        for i, r in enumerate(ranked[:max_results])
    ]

    nearest_mandi = pick_nearest(ranked)

    forecast_used = any(r.price_basis == "forecast" for r in ranked)
    caveats = _price_status_caveat(snapshot_date)
    if forecast_used and fc_engine is not None:
        caveats.insert(
            0,
            "Revenue uses a price forecast for the arrival day (1-3 days ahead, from transit time): "
            f"the median, with a likely range, from a model trained on data through "
            f"{fc_engine.trained_through}. Mandis without enough recent price history use "
            "today's quote instead.",
        )

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
        nearest_mandi=nearest_mandi,
        infeasible=sorted(infeasible, key=lambda x: x.distance_km)[:max_results],
        caveats=caveats,
        forecast_used=forecast_used,
        forecast_model_trained_through=(
            fc_engine.trained_through if (forecast_used and fc_engine is not None) else None
        ),
    )
