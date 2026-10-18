"""Market intelligence endpoints.

GET /intel/commodity-summary?commodity=X
    National price statistics + state rankings for one commodity today.
    Useful for: "where is Tomato paying the most right now?"

GET /intel/commodity-overview
    One-row summary per commodity (national median, peak, top state).
    Powers the multi-commodity home-page widget.

GET /intel/net-spread?commodity=X&lat=Y&lon=Z&vehicle=...&diesel=...&qty=...
    All reachable mandis within radius, ranked by NET price per quintal
    after freight + APMC + cess + labour. Per-quintal because farmers
    think in quintals, not tonnes.
    Useful for: "show me every market I can reach and what I actually pocket."
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.analysis.market_intelligence import (
    commodity_overview,
    commodity_stats,
    state_price_rankings,
)
from backend.api.dependencies import get_db
from backend.api.schemas import (
    CommodityOverviewItem,
    CommodityOverviewResponse,
    CommoditySummaryResponse,
    NetMarketRow,
    NetSpreadResponse,
    StateRankRow,
)
from backend.cost.model import QUINTALS_PER_TONNE, load_state_costs
from backend.decision.geo import estimated_road_km, resolve_centroid
from backend.decision.spoilage import DEFAULT_AMBIENT_C, estimate_spoilage
from backend.decision.vehicles import fuel_line, get_vehicle, other_freight_rs, transit_hours

router = APIRouter(prefix="/intel", tags=["intelligence"])

_PRICE_FLOOR = 100.0  # ₹/quintal — consistent with markets.py and recommender.py


@router.get("/commodity-summary", response_model=CommoditySummaryResponse)
def commodity_summary(
    commodity: str = Query(..., description="Exact commodity name (case-sensitive)"),
    db: Session = Depends(get_db),
) -> CommoditySummaryResponse:
    """National price stats + all-state ranking for one commodity."""
    stats = commodity_stats(db, commodity)
    if stats is None:
        raise HTTPException(
            status_code=404, detail=f"No data for commodity '{commodity}'"
        )
    rankings = state_price_rankings(db, commodity)
    return CommoditySummaryResponse(
        commodity=stats.commodity,
        snapshot_date=stats.snapshot_date,
        national_median=stats.national_median,
        p25=stats.p25,
        p75=stats.p75,
        national_max=stats.national_max,
        national_min=stats.national_min,
        mandis_count=stats.mandis_count,
        states_count=stats.states_count,
        state_rankings=[
            StateRankRow(
                state=r.state,
                median_price=r.median_price,
                max_price=r.max_price,
                min_price=r.min_price,
                mandis_reporting=r.mandis_reporting,
                rank=r.rank,
            )
            for r in rankings
        ],
    )


@router.get("/commodity-overview", response_model=CommodityOverviewResponse)
def overview(db: Session = Depends(get_db)) -> CommodityOverviewResponse:
    """One-row summary per commodity for the dashboard home widget."""
    rows = commodity_overview(db)
    if not rows:
        raise HTTPException(status_code=404, detail="market_daily is empty")
    return CommodityOverviewResponse(
        snapshot_date=rows[0].snapshot_date,
        commodities=[
            CommodityOverviewItem(
                commodity=r.commodity,
                national_median=r.national_median,
                national_max=r.national_max,
                mandis_count=r.mandis_count,
                best_state=r.best_state,
                best_state_median=r.best_state_median,
            )
            for r in rows
        ],
    )


@router.get("/net-spread", response_model=NetSpreadResponse)
def net_spread(
    commodity: str = Query(..., description="Exact commodity name (case-sensitive)"),
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    vehicle: str = Query("truck_small"),
    diesel_price_rs_per_l: float = Query(95.0, gt=0),
    quantity_tonnes: float = Query(5.0, gt=0),
    radius_km: float = Query(250.0, gt=0, le=500),
    ambient_c: float = Query(DEFAULT_AMBIENT_C, ge=-10, le=55),
    db: Session = Depends(get_db),
) -> NetSpreadResponse:
    """All reachable mandis ranked by NET price per quintal after all costs.

    Unlike /recommend (top-8, full cost breakdown), this returns every mandi
    within the radius with a compact per-quintal view — useful for a map
    overlay or full comparison table in the UI.
    """
    try:
        veh = get_vehicle(vehicle)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Pull latest modal prices for this commodity
    latest = db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()
    if latest is None:
        raise HTTPException(status_code=404, detail="market_daily is empty")

    rows = db.execute(
        text("""
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
            WHERE md.date         = :d
              AND c.name          = :commodity
              AND md.modal_price >= :floor
            ORDER BY md.modal_price DESC
        """),
        {"d": latest, "commodity": commodity, "floor": _PRICE_FLOOR},
    ).mappings().all()

    if not rows:
        raise HTTPException(
            status_code=404, detail=f"No data for commodity '{commodity}'"
        )

    state_costs = load_state_costs()
    markets: list[NetMarketRow] = []

    for row in rows:
        centroid = resolve_centroid(row["state"], row["district"])
        if centroid is None:
            continue
        distance = estimated_road_km(
            origin_lat, origin_lon, centroid.latitude, centroid.longitude
        )
        if distance > radius_km:
            continue

        rates = state_costs.get(row["state"])
        if rates is None:
            continue

        hours = transit_hours(distance, veh)
        spoilage = estimate_spoilage(
            commodity=commodity,
            transit_hours=hours,
            vehicle=veh,
            ambient_c=ambient_c,
        )
        feasible = spoilage is not None and spoilage.feasible
        spoilage_pct = round(spoilage.spoilage_fraction * 100, 1) if spoilage else 100.0

        modal = float(row["modal_price"])
        qty_qtls = quantity_tonnes * QUINTALS_PER_TONNE

        _, fuel_rs = fuel_line(distance, veh, diesel_price_rs_per_l)
        other_frt = other_freight_rs(distance, veh, quantity_tonnes, diesel_price_rs_per_l)
        freight_per_qtl = round((fuel_rs + other_frt) / qty_qtls, 1)

        apmc = modal * rates.apmc_commission_pct / 100
        cess = modal * rates.cess_pct / 100
        entry = rates.entry_fee_rs_per_tonne / QUINTALS_PER_TONNE
        labour = rates.labour_rs_per_tonne / QUINTALS_PER_TONNE
        weighment = rates.weighment_rs_per_tonne / QUINTALS_PER_TONNE
        fees_per_qtl = round(apmc + cess + entry + labour + weighment, 1)

        # Spoilage discount applies to the effective modal price
        effective_modal = modal * (1.0 - spoilage_pct / 100.0) if feasible else modal
        net_per_qtl = round(effective_modal - freight_per_qtl - fees_per_qtl, 1)

        markets.append(
            NetMarketRow(
                market_id=int(row["market_id"]),
                market_name=row["market_name"],
                district=row["district"] or "",
                state=row["state"],
                distance_km=round(distance, 1),
                modal_price_rs_per_qtl=modal,
                net_price_rs_per_qtl=net_per_qtl,
                freight_rs_per_qtl=freight_per_qtl,
                fees_rs_per_qtl=fees_per_qtl,
                spoilage_pct=spoilage_pct,
                feasible=feasible,
            )
        )

    # Sort: feasible first, then by net price descending
    markets.sort(key=lambda m: (not m.feasible, -m.net_price_rs_per_qtl))

    feasible_nets = [m.net_price_rs_per_qtl for m in markets if m.feasible]
    best_net = max(feasible_nets) if feasible_nets else 0.0
    median_net = sorted(feasible_nets)[len(feasible_nets) // 2] if feasible_nets else 0.0
    uplift_pct = (
        round((best_net - median_net) / median_net * 100, 1)
        if median_net > 0
        else 0.0
    )

    return NetSpreadResponse(
        commodity=commodity,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        radius_km=radius_km,
        snapshot_date=latest,
        total_markets=len(markets),
        feasible_count=len(feasible_nets),
        best_net_price=best_net,
        median_net_price=median_net,
        potential_uplift_pct=uplift_pct,
        markets=markets,
    )
