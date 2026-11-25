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
    # Price context — how does this mandi compare to others?
    price_pct_rank_in_state: float = Field(
        50.0,
        description="Percentile rank of this mandi's price within its state (0=cheapest, 100=priciest).",
    )
    vs_state_median_rs_per_qtl: float = Field(
        0.0,
        description="Premium over state median (₹/qtl). Negative = below median.",
    )
    vs_national_median_rs_per_qtl: float = Field(
        0.0,
        description="Premium over national median (₹/qtl). Negative = below median.",
    )

    # Forecast. `modal_price_rs_per_quintal` is TODAY'S quote; revenue is computed from
    # `expected_price_rs_per_quintal` (the P50 forecast for the arrival day when available).
    expected_price_rs_per_quintal: float = Field(
        0.0, description="Price the revenue is computed from (₹/qtl)."
    )
    price_basis: str = Field(
        "snapshot", description="'forecast' (P50 for the arrival day) or 'snapshot' (today's quote)."
    )
    forecast_horizon_days: int | None = None
    forecast_p10_rs_per_quintal: float | None = Field(
        None, description="Pessimistic price: 1 in 10 chance it lands below this (₹/qtl)."
    )
    forecast_p90_rs_per_quintal: float | None = Field(
        None, description="Optimistic price: 1 in 10 chance it lands above this (₹/qtl)."
    )
    net_rs_per_tonne_p10: float | None = Field(
        None, description="Net ₹/tonne if the price lands at the forecast P10."
    )
    net_rs_per_tonne_p90: float | None = Field(
        None, description="Net ₹/tonne if the price lands at the forecast P90."
    )


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
    forecast_used: bool = False
    forecast_model_trained_through: str | None = None
    infeasible: list[RecommendationInfeasible]
    ranked: list[RecommendationItem]
    nearest_mandi: RecommendationItem | None = Field(
        None,
        description="Closest mandi by distance among ranked results. "
        "If different from ranked[0], the farmer is leaving money on the table.",
    )


# ── Forecast ──────────────────────────────────────────────────────────────────

class ForecastBacktestRow(BaseModel):
    horizon_days: int
    model: str
    pinball_loss: float
    skill_vs_naive: float = Field(description="Pinball-loss improvement over 'tomorrow = today' (+ = better).")
    mae_rs_per_quintal: float
    coverage_p10_p90: float = Field(description="Share of actual prices inside [P10, P90]; ideal 0.80.")
    band_width_pct: float
    test_rows: int


class ForecastInfoResponse(BaseModel):
    available: bool
    trained_through: str | None = None
    horizons: list[int] = []
    backtest: list[ForecastBacktestRow] = []
    note: str | None = None


# ── Intelligence endpoints ────────────────────────────────────────────────────

class StateRankRow(BaseModel):
    state: str
    median_price: float
    max_price: float
    min_price: float
    mandis_reporting: int
    rank: int


class CommoditySummaryResponse(BaseModel):
    """National price statistics + state rankings for one commodity."""
    commodity: str
    snapshot_date: date | None
    national_median: float
    p25: float
    p75: float
    national_max: float
    national_min: float
    mandis_count: int
    states_count: int
    state_rankings: list[StateRankRow]


class CommodityOverviewItem(BaseModel):
    commodity: str
    national_median: float
    national_max: float
    mandis_count: int
    best_state: str
    best_state_median: float


class CommodityOverviewResponse(BaseModel):
    """One-row summary per commodity for the dashboard home widget."""
    snapshot_date: date | None
    commodities: list[CommodityOverviewItem]


class NetMarketRow(BaseModel):
    """A single mandi with freight-adjusted net price per quintal."""
    market_id: int
    market_name: str
    district: str
    state: str
    distance_km: float
    modal_price_rs_per_qtl: float = Field(description="Raw mandi price (₹/qtl)")
    net_price_rs_per_qtl: float = Field(description="After freight + all fees (₹/qtl)")
    freight_rs_per_qtl: float
    fees_rs_per_qtl: float = Field(description="APMC + cess + entry + labour + weighment (₹/qtl)")
    spoilage_pct: float
    feasible: bool


class NetSpreadResponse(BaseModel):
    """All reachable mandis for a farmer's location, ranked by net price."""
    commodity: str
    origin_lat: float
    origin_lon: float
    radius_km: float
    snapshot_date: date | None
    total_markets: int
    feasible_count: int
    best_net_price: float = Field(description="Highest net ₹/qtl among feasible mandis")
    median_net_price: float
    potential_uplift_pct: float = Field(
        description="% gain of best mandi vs median net price"
    )
    markets: list[NetMarketRow]


# ── Geo endpoints ─────────────────────────────────────────────────────────────

class DistrictRow(BaseModel):
    district: str
    lat: float
    lon: float


class DistrictsResponse(BaseModel):
    state: str
    count: int
    districts: list[DistrictRow]


# ── Seasonal intelligence ─────────────────────────────────────────────────────

class SeasonalWeek(BaseModel):
    iso_week: int
    arrival_index: float
    label: str = Field(description="glut | lean | normal")


class SeasonalResponse(BaseModel):
    available: bool
    reason: str | None = None
    commodity: str | None = None
    state: str | None = None
    current_week: int | None = None
    weeks: list[SeasonalWeek] = []
