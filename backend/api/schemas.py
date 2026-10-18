"""Pydantic response schemas for the read-only demo API.

Kept in one file because the surface is small. If it grows past ~15 models,
split by router.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SummaryCard(BaseModel):
    label: str
    value: str
    caption: str | None = None


class SummaryResponse(BaseModel):
    snapshot_date: date | None
    cards: list[SummaryCard]


class MandiPrice(BaseModel):
    market_id: int
    state: str
    district: str
    market: str
    commodity: str
    variety: str | None
    modal_price_rs_per_quintal: float
    min_price_rs_per_quintal: float | None
    max_price_rs_per_quintal: float | None
    date: date


class MandiPriceList(BaseModel):
    commodity: str
    state: str | None
    snapshot_date: date | None
    count: int
    rows: list[MandiPrice]


class ArbitrageRow(BaseModel):
    commodity: str
    state: str
    snapshot_date: date
    mandis_reporting: int
    min_price_rs_per_quintal: float
    max_price_rs_per_quintal: float
    spread_rs_per_quintal: float
    spread_pct: float
    high_market: str = Field(description="Mandi reporting the maximum price")
    low_market: str = Field(description="Mandi reporting the minimum price")


class ArbitrageResponse(BaseModel):
    snapshot_date: date | None
    count: int
    rows: list[ArbitrageRow]


class Facets(BaseModel):
    commodities: list[str]
    states: list[str]


class CostLineItem(BaseModel):
    label: str
    amount_rs: float


class CostEstimateResponse(BaseModel):
    quote_price_rs_per_quintal: float
    quantity_tonnes: float
    distance_km: float
    dest_state: str
    diesel_price_rs_per_l: float
    truck_size_tonnes: float

    gross_revenue_rs: float
    deductions: list[CostLineItem]
    total_deductions_rs: float
    net_revenue_rs: float
    net_rs_per_tonne: float


# ── Phase 5: Recommendation surface ──────────────────────────────────────────

class VehicleSpec(BaseModel):
    key: str
    label: str
    capacity_tonnes: float
    mileage_kmpl: float
    avg_speed_kmph: float
    insulation: str
    notes: str


class VehicleCatalogueResponse(BaseModel):
    vehicles: list[VehicleSpec]


class RecommendationSpoilage(BaseModel):
    ambient_c: float
    effective_c: float
    sl_opt_days: float
    sl_at_effective_days: float
    spoilage_fraction: float
    feasible: bool
    reason: str


class RecommendationCostBreakdown(BaseModel):
    fuel_litres: float
    fuel_rs: float
    other_freight_rs: float
    apmc_commission_rs: float
    cess_rs: float
    entry_fee_rs: float
    labour_rs: float
    weighment_rs: float
    total_deductions_rs: float


class RecommendationItem(BaseModel):
    rank: int
    market_id: int
    market_name: str
    district: str
    state: str
    distance_km: float
    distance_source: str
    transit_hours: float
    trips: int
    modal_price_rs_per_quintal: float
    gross_revenue_rs: float
    expected_saleable_revenue_rs: float
    net_revenue_rs: float
    net_rs_per_tonne: float
    price_status: str
    price_snapshot_date: date
    why: str
    costs: RecommendationCostBreakdown
    spoilage: RecommendationSpoilage


class RecommendationInfeasible(BaseModel):
    market_name: str
    district: str
    state: str
    distance_km: float
    reason: str


class RecommendationResponse(BaseModel):
    origin_lat: float
    origin_lon: float
    radius_km: float
    commodity: str
    quantity_tonnes: float
    vehicle_key: str
    vehicle_label: str
    diesel_price_rs_per_l: float
    ambient_c: float
    snapshot_date: date | None
    considered: int
    caveats: list[str]
    infeasible: list[RecommendationInfeasible]
    ranked: list[RecommendationItem]
