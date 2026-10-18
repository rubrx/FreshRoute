"""GET /recommend — the farmer-facing routing decision.

Takes an origin (lat/lon), a commodity, a quantity, a vehicle, and a
diesel price. Returns the ranked list of feasible mandis and the
infeasible ones with reasons.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.api.schemas import (
    RecommendationCostBreakdown,
    RecommendationInfeasible,
    RecommendationItem,
    RecommendationResponse,
    RecommendationSpoilage,
    VehicleSpec,
    VehicleCatalogueResponse,
)
from backend.decision.recommender import DEFAULT_MAX_RESULTS, DEFAULT_RADIUS_KM, recommend
from backend.decision.spoilage import DEFAULT_AMBIENT_C
from backend.decision.vehicles import VEHICLE_CATALOGUE, get_vehicle, list_vehicles

router = APIRouter(tags=["recommend"])


@router.get("/recommend/vehicles", response_model=VehicleCatalogueResponse)
def vehicles() -> VehicleCatalogueResponse:
    """Static catalogue for the UI's vehicle picker."""
    return VehicleCatalogueResponse(
        vehicles=[
            VehicleSpec(
                key=v.key,
                label=v.label,
                capacity_tonnes=v.capacity_tonnes,
                mileage_kmpl=v.mileage_kmpl,
                avg_speed_kmph=v.avg_speed_kmph,
                insulation=v.insulation,
                notes=v.notes,
            )
            for v in list_vehicles()
        ]
    )


@router.get("/recommend", response_model=RecommendationResponse)
def recommend_route(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    commodity: str = Query(..., description="Exact commodity name (Tomato/Onion/…)."),
    quantity_tonnes: float = Query(..., gt=0),
    vehicle: str = Query("truck_small", description=f"One of: {list(VEHICLE_CATALOGUE)}"),
    diesel_price_rs_per_l: float = Query(95.0, gt=0),
    ambient_c: float = Query(DEFAULT_AMBIENT_C, ge=-10, le=55),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=500),
    max_results: int = Query(DEFAULT_MAX_RESULTS, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    try:
        vehicle_spec = get_vehicle(vehicle)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = recommend(
        db=db,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        commodity=commodity,
        quantity_tonnes=quantity_tonnes,
        vehicle=vehicle_spec,
        diesel_price_rs_per_l=diesel_price_rs_per_l,
        ambient_c=ambient_c,
        radius_km=radius_km,
        max_results=max_results,
    )

    return RecommendationResponse(
        origin_lat=result.origin_lat,
        origin_lon=result.origin_lon,
        radius_km=result.radius_km,
        commodity=result.commodity,
        quantity_tonnes=result.quantity_tonnes,
        vehicle_key=result.vehicle_key,
        vehicle_label=vehicle_spec.label,
        diesel_price_rs_per_l=result.diesel_price_rs_per_l,
        ambient_c=result.ambient_c,
        snapshot_date=result.snapshot_date,
        considered=result.considered,
        caveats=result.caveats,
        infeasible=[
            RecommendationInfeasible(
                market_name=i.market_name,
                district=i.district,
                state=i.state,
                distance_km=i.distance_km,
                reason=i.reason,
            )
            for i in result.infeasible
        ],
        ranked=[
            RecommendationItem(
                rank=r.rank,
                market_id=r.market_id,
                market_name=r.market_name,
                district=r.district,
                state=r.state,
                distance_km=r.distance_km,
                distance_source=r.distance_source,
                transit_hours=r.transit_hours,
                trips=r.trips,
                modal_price_rs_per_quintal=r.modal_price_rs_per_quintal,
                gross_revenue_rs=r.gross_revenue_rs,
                expected_saleable_revenue_rs=r.expected_saleable_revenue_rs,
                net_revenue_rs=r.net_revenue_rs,
                net_rs_per_tonne=r.net_rs_per_tonne,
                price_status=r.price_status,
                price_snapshot_date=r.price_snapshot_date,
                why=r.why,
                costs=RecommendationCostBreakdown(
                    fuel_litres=r.costs.fuel_litres,
                    fuel_rs=r.costs.fuel_rs,
                    other_freight_rs=r.costs.other_freight_rs,
                    apmc_commission_rs=r.costs.apmc_commission_rs,
                    cess_rs=r.costs.cess_rs,
                    entry_fee_rs=r.costs.entry_fee_rs,
                    labour_rs=r.costs.labour_rs,
                    weighment_rs=r.costs.weighment_rs,
                    total_deductions_rs=r.costs.total_deductions_rs,
                ),
                spoilage=RecommendationSpoilage(
                    ambient_c=r.spoilage.ambient_c,
                    effective_c=r.spoilage.effective_c,
                    sl_opt_days=r.spoilage.sl_opt_days,
                    sl_at_effective_days=r.spoilage.sl_at_effective_days,
                    spoilage_fraction=r.spoilage.spoilage_fraction,
                    feasible=r.spoilage.feasible,
                    reason=r.spoilage.reason,
                ),
            )
            for r in result.ranked
        ],
    )
