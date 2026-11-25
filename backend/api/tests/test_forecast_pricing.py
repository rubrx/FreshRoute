"""Tests for pricing a load at a forecast price (revenue, fees, and the P10/P90 net range)."""

from __future__ import annotations

from datetime import date

import pytest

from backend.decision.recommender import choose_snapshot, price_outcome


def test_a_thin_partial_snapshot_is_not_treated_as_today():
    # Real counts: the Nov 22 pull ran early and caught only 41 mandis; a normal day has ~1,700.
    counts = [(date(2026, 11, 22), 41), (date(2026, 11, 21), 1705),
              (date(2026, 11, 20), 1933), (date(2026, 11, 3), 1738)]
    assert choose_snapshot(counts) == date(2026, 11, 21)


def test_the_newest_day_is_used_when_it_is_complete():
    counts = [(date(2026, 11, 22), 1650), (date(2026, 11, 21), 1705)]
    assert choose_snapshot(counts) == date(2026, 11, 22)


def test_snapshot_choice_handles_no_data_and_uniformly_small_data():
    assert choose_snapshot([]) is None
    assert choose_snapshot([(date(2026, 11, 21), 3), (date(2026, 11, 20), 4)]) == date(2026, 11, 21)


def test_price_outcome_matches_a_hand_calculation():
    # 5 t sold at Rs 2,000/qtl (= Rs 20,000/t) -> gross Rs 100,000
    gross, saleable, apmc, cess, net = price_outcome(
        price_rs_qtl=2000, quantity_tonnes=5, spoilage_fraction=0.10,
        apmc_pct=1.5, cess_pct=0.5, fixed_rs=4000,
    )
    assert gross == pytest.approx(100_000)
    assert saleable == pytest.approx(90_000)      # 10% spoiled
    assert apmc == pytest.approx(1_500)           # % of gross
    assert cess == pytest.approx(500)
    assert net == pytest.approx(90_000 - 4_000 - 1_500 - 500)


def test_a_lower_forecast_percentile_means_a_lower_net():
    kwargs = dict(quantity_tonnes=5, spoilage_fraction=0.05, apmc_pct=2.0, cess_pct=1.0,
                  fixed_rs=6000)
    p10 = price_outcome(1800, **kwargs)[-1]
    p50 = price_outcome(2000, **kwargs)[-1]
    p90 = price_outcome(2300, **kwargs)[-1]
    assert p10 < p50 < p90


def test_fixed_costs_do_not_scale_with_price_but_fees_do():
    base = dict(quantity_tonnes=1, spoilage_fraction=0.0, apmc_pct=2.0, cess_pct=0.0)
    cheap = price_outcome(1000, fixed_rs=500, **base)
    dear = price_outcome(2000, fixed_rs=500, **base)
    assert dear[2] == pytest.approx(2 * cheap[2])                 # apmc doubles with gross
    # net grows by more than the gross change would suggest only if fees were fixed;
    # here: gross +10,000, apmc +200 -> net +9,800
    assert dear[-1] - cheap[-1] == pytest.approx(10_000 - 200)


def test_without_spoilage_or_fees_net_is_gross_minus_fixed_costs():
    gross, saleable, apmc, cess, net = price_outcome(
        3000, quantity_tonnes=2, spoilage_fraction=0.0, apmc_pct=0.0, cess_pct=0.0, fixed_rs=1234)
    assert gross == saleable == pytest.approx(60_000)
    assert apmc == cess == 0
    assert net == pytest.approx(60_000 - 1234)
