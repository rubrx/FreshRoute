"""Tests for the "nearest mandi" baseline in the recommender."""

from __future__ import annotations

from datetime import date

from backend.decision.recommender import (
    CostBreakdown,
    Recommendation,
    pick_nearest,
)
from backend.decision.spoilage import SpoilageEstimate


def _make_rec(rank: int, distance_km: float, net: float) -> Recommendation:
    spoilage = SpoilageEstimate(
        ambient_c=30.0,
        effective_c=28.0,
        sl_opt_days=14.0,
        sl_at_effective_days=3.38,
        transit_hours=3.0,
        dwell_factor=1.35,
        fraction_of_shelf_life_used=0.05,
        spoilage_fraction=0.05,
        feasible=True,
        reason="ok",
    )
    costs = CostBreakdown(
        fuel_litres=10.0,
        fuel_rs=950.0,
        other_freight_rs=200.0,
        apmc_commission_rs=300.0,
        cess_rs=50.0,
        entry_fee_rs=20.0,
        labour_rs=40.0,
        weighment_rs=10.0,
        total_deductions_rs=1570.0,
    )
    return Recommendation(
        rank=rank,
        market_id=rank,
        market_name=f"Mandi{rank}",
        district="D",
        state="S",
        distance_km=distance_km,
        distance_source="district",
        transit_hours=3.0,
        trips=1,
        modal_price_rs_per_quintal=2500.0,
        quantity_tonnes=5.0,
        gross_revenue_rs=125000.0,
        expected_saleable_revenue_rs=118750.0,
        costs=costs,
        net_revenue_rs=net * 5,
        net_rs_per_tonne=net,
        spoilage=spoilage,
        price_status="live",
        price_snapshot_date=date(2026, 9, 8),
        why="test",
    )


def test_nearest_mandi_is_closest_not_highest():
    # rank 1 = best net but far; rank 2 = lower net but closer
    r1 = _make_rec(1, distance_km=200.0, net=25000.0)
    r2 = _make_rec(2, distance_km=50.0, net=22000.0)

    nearest = pick_nearest([r1, r2])

    assert nearest is r2
    assert nearest.distance_km == 50.0


def test_nearest_mandi_can_be_the_top_ranked():
    r1 = _make_rec(1, distance_km=30.0, net=25000.0)
    r2 = _make_rec(2, distance_km=120.0, net=22000.0)

    assert pick_nearest([r1, r2]) is r1


def test_nearest_mandi_is_none_when_nothing_ranked():
    assert pick_nearest([]) is None
