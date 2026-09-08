"""Tests for the cost model.

The model is a pure function of the reference CSVs. Tests use the shipped
CSVs (no fixtures) so they catch inadvertent breakage of the reference
values as well as code regressions.
"""

from __future__ import annotations

import pytest

from backend.cost.model import (
    QUINTALS_PER_TONNE,
    _DIESEL_SENSITIVITY,
    FreightSpec,
    load_freight_table,
    load_state_costs,
    net_realization,
    pick_truck,
)


class TestPickTruck:
    def test_returns_smallest_truck_that_fits(self):
        assert pick_truck(2.0).truck_size_tonnes == 3.0
        assert pick_truck(5.0).truck_size_tonnes == 7.0
        assert pick_truck(8.0).truck_size_tonnes == 10.0
        assert pick_truck(12.0).truck_size_tonnes == 16.0

    def test_exact_match_uses_that_truck(self):
        assert pick_truck(10.0).truck_size_tonnes == 10.0

    def test_oversized_falls_back_to_largest(self):
        biggest = load_freight_table()[-1]
        assert pick_truck(999.0).truck_size_tonnes == biggest.truck_size_tonnes

    def test_zero_or_negative_rejected(self):
        with pytest.raises(ValueError):
            pick_truck(0)
        with pytest.raises(ValueError):
            pick_truck(-1)


class TestNetRealization:
    def test_deductions_sum_matches_gross_minus_net(self):
        b = net_realization(
            quote_price_rs_per_quintal=2000,
            quantity_tonnes=8,
            distance_km=350,
            dest_state="Maharashtra",
            diesel_price_rs_per_l=95.0,
        )
        assert b.gross_revenue_rs == pytest.approx(
            b.net_revenue_rs + b.total_deductions_rs, rel=1e-6
        )
        line_sum = (
            b.freight_rs + b.apmc_commission_rs + b.cess_rs
            + b.entry_fee_rs + b.labour_rs + b.weighment_rs
        )
        assert b.total_deductions_rs == pytest.approx(line_sum, rel=1e-6)

    def test_gross_uses_quintal_conversion(self):
        b = net_realization(
            quote_price_rs_per_quintal=1000,
            quantity_tonnes=5,
            distance_km=100,
            dest_state="Karnataka",
            diesel_price_rs_per_l=90.0,
        )
        # 1000 ₹/qtl × 10 qtl/tonne × 5 tonnes = 50,000
        assert b.gross_revenue_rs == pytest.approx(1000 * QUINTALS_PER_TONNE * 5)

    def test_apmc_commission_is_percent_of_gross(self):
        rates = load_state_costs()["Maharashtra"]
        b = net_realization(
            quote_price_rs_per_quintal=1500,
            quantity_tonnes=10,
            distance_km=0,
            dest_state="Maharashtra",
            diesel_price_rs_per_l=90.0,
        )
        expected = b.gross_revenue_rs * (rates.apmc_commission_pct / 100.0)
        assert b.apmc_commission_rs == pytest.approx(expected)

    def test_zero_distance_still_incurs_fixed_loading(self):
        b = net_realization(
            quote_price_rs_per_quintal=1500,
            quantity_tonnes=8,
            distance_km=0,
            dest_state="Karnataka",
            diesel_price_rs_per_l=90.0,
        )
        truck = pick_truck(8)
        assert b.freight_rs == pytest.approx(truck.fixed_loading_rs)

    def test_diesel_price_scales_freight_partially(self):
        common = dict(
            quote_price_rs_per_quintal=1500,
            quantity_tonnes=8,
            distance_km=500,
            dest_state="Karnataka",
        )
        at_ref = net_realization(**common, diesel_price_rs_per_l=90.0)
        expensive = net_realization(**common, diesel_price_rs_per_l=180.0)  # 2x

        truck = pick_truck(8)
        km_component_at_ref = truck.rs_per_km_base * 500
        expected_delta = _DIESEL_SENSITIVITY * km_component_at_ref
        assert (expensive.freight_rs - at_ref.freight_rs) == pytest.approx(expected_delta)

    def test_higher_quantity_needs_more_trips(self):
        common = dict(
            quote_price_rs_per_quintal=1500,
            distance_km=200,
            dest_state="Maharashtra",
            diesel_price_rs_per_l=90.0,
        )
        # Both should pick the 25-tonne truck (largest); 20t → 1 trip, 30t → 2 trips.
        big = net_realization(**common, quantity_tonnes=20, truck=load_freight_table()[-1])
        bigger = net_realization(**common, quantity_tonnes=30, truck=load_freight_table()[-1])
        assert bigger.freight_rs > big.freight_rs

    def test_unknown_state_raises_keyerror(self):
        with pytest.raises(KeyError):
            net_realization(
                quote_price_rs_per_quintal=1000,
                quantity_tonnes=5,
                distance_km=100,
                dest_state="Atlantis",
                diesel_price_rs_per_l=90.0,
            )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValueError):
            net_realization(
                quote_price_rs_per_quintal=1000,
                quantity_tonnes=0,
                distance_km=100,
                dest_state="Karnataka",
                diesel_price_rs_per_l=90.0,
            )

    def test_negative_distance_rejected(self):
        with pytest.raises(ValueError):
            net_realization(
                quote_price_rs_per_quintal=1000,
                quantity_tonnes=5,
                distance_km=-1,
                dest_state="Karnataka",
                diesel_price_rs_per_l=90.0,
            )

    def test_per_tonne_matches_total_divided_by_quantity(self):
        b = net_realization(
            quote_price_rs_per_quintal=1800,
            quantity_tonnes=7.5,
            distance_km=420,
            dest_state="Delhi",
            diesel_price_rs_per_l=98.0,
        )
        assert b.net_rs_per_tonne == pytest.approx(b.net_revenue_rs / 7.5, rel=1e-6)


class TestReferenceData:
    """Guard rails on the CSVs so silent edits don't destroy the ranker."""

    def test_all_states_have_valid_rates(self):
        for state, rates in load_state_costs().items():
            assert 0 <= rates.apmc_commission_pct <= 15, state
            assert 0 <= rates.cess_pct <= 10, state
            assert rates.entry_fee_rs_per_tonne >= 0, state
            assert rates.labour_rs_per_tonne > 0, state

    def test_freight_table_is_sorted_and_monotonic(self):
        table = load_freight_table()
        sizes = [t.truck_size_tonnes for t in table]
        assert sizes == sorted(sizes)
        # Bigger trucks should cost more per km than smaller ones (economies
        # of scale flip in per-tonne, not per-km).
        rates = [t.rs_per_km_base for t in table]
        assert rates == sorted(rates)
