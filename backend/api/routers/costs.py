"""POST /cost/estimate — itemized ₹ breakdown for a hypothetical consignment.

Thin wrapper over `backend.cost.model.net_realization`. The model is already
covered by 13 pytest cases; the router only translates query params and
formats the response.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import CostEstimateResponse, CostLineItem
from backend.cost.model import net_realization

router = APIRouter(tags=["costs"])


@router.get("/cost/estimate", response_model=CostEstimateResponse)
def estimate(
    quote_price_rs_per_quintal: float = Query(..., gt=0),
    quantity_tonnes: float = Query(..., gt=0),
    distance_km: float = Query(..., ge=0),
    dest_state: str = Query(...),
    diesel_price_rs_per_l: float = Query(95.0, gt=0,
                                         description="Today's diesel; ₹ scales linearly"),
) -> CostEstimateResponse:
    try:
        cb = net_realization(
            quote_price_rs_per_quintal=quote_price_rs_per_quintal,
            quantity_tonnes=quantity_tonnes,
            distance_km=distance_km,
            dest_state=dest_state,
            diesel_price_rs_per_l=diesel_price_rs_per_l,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    deductions = [
        CostLineItem(label="Freight",         amount_rs=cb.freight_rs),
        CostLineItem(label="APMC commission", amount_rs=cb.apmc_commission_rs),
        CostLineItem(label="Cess",            amount_rs=cb.cess_rs),
        CostLineItem(label="Entry fee",       amount_rs=cb.entry_fee_rs),
        CostLineItem(label="Labour",          amount_rs=cb.labour_rs),
        CostLineItem(label="Weighment",       amount_rs=cb.weighment_rs),
    ]
    return CostEstimateResponse(
        quote_price_rs_per_quintal=cb.quote_price_rs_per_quintal,
        quantity_tonnes=cb.quantity_tonnes,
        distance_km=cb.distance_km,
        dest_state=cb.dest_state,
        diesel_price_rs_per_l=cb.diesel_price_rs_per_l,
        truck_size_tonnes=cb.truck_size_tonnes,
        gross_revenue_rs=cb.gross_revenue_rs,
        deductions=deductions,
        total_deductions_rs=cb.total_deductions_rs,
        net_revenue_rs=cb.net_revenue_rs,
        net_rs_per_tonne=cb.net_rs_per_tonne,
    )
