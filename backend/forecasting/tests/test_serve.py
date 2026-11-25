"""Tests for serving forecasts: gating rules, plausibility guard, and graceful fallback."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.forecasting.backtest import split_for_fold
from backend.forecasting.features import make_dataset
from backend.forecasting.model import Forecaster
from backend.forecasting.panel import clean_series
from backend.forecasting.serve import (
    MIN_RECENT_OBS,
    forecast_from_series,
    get_forecaster,
    horizon_days_for_hours,
)
from backend.forecasting.tests.test_forecasting import synthetic_panel


@pytest.fixture(scope="module")
def trained():
    """A small model trained on 2019-2022 of one synthetic commodity, plus its full series."""
    panel = synthetic_panel(seed=11, years=5, markets_per_state=5)
    series = clean_series(panel)
    series = series[series["commodity"] == "Tomato"]
    ds, enc = make_dataset(series)
    train, _ = split_for_fold(ds, 1, pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"))
    model = Forecaster.fit(train, enc, horizons=(1, 2, 3), rounds=40)
    return model, series


def _as_of_with_reporters(series: pd.DataFrame, minimum: int = 4) -> pd.Timestamp:
    counts = series[series["date"] >= "2023-03-01"].groupby("date")["market_id"].nunique()
    return counts[counts >= minimum].index[10]


def test_horizon_is_one_day_for_a_same_day_trip_and_grows_with_transit_time():
    assert horizon_days_for_hours(0.5) == 1
    assert horizon_days_for_hours(6) == 1
    assert horizon_days_for_hours(23.9) == 1
    assert horizon_days_for_hours(24) == 2
    assert horizon_days_for_hours(47) == 2
    assert horizon_days_for_hours(48) == 3
    assert horizon_days_for_hours(500) == 3          # never beyond what the model was trained for


def test_forecasts_exist_only_for_mandis_that_reported_on_the_snapshot_day(trained):
    model, series = trained
    as_of = _as_of_with_reporters(series)
    history = series[series["date"] <= as_of]            # what the database holds on that day

    out = forecast_from_series(model, history, as_of.date())

    reported = set(history.loc[history["date"] == as_of, "market_id"])
    assert out, "expected forecasts for mandis that reported"
    assert {m for m, _ in out} <= reported
    assert {h for _, h in out} == {1, 2, 3}


def test_forecast_bands_are_ordered_and_close_to_todays_price(trained):
    model, series = trained
    as_of = _as_of_with_reporters(series)
    out = forecast_from_series(model, series[series["date"] <= as_of], as_of.date())

    for fc in out.values():
        assert fc.p10 <= fc.p50 <= fc.p90
        assert fc.p10 > 0
        assert abs(np.log(fc.p50 / fc.today_price)) < 0.5


def test_a_mandi_with_too_little_recent_history_gets_no_forecast(trained):
    model, series = trained
    as_of = _as_of_with_reporters(series)
    history = series[series["date"] <= as_of]
    victim = int(history.loc[history["date"] == as_of, "market_id"].iloc[0])

    # leave the victim with only today's report in the last 28 days
    recent = (history["market_id"] == victim) & (history["date"] < as_of) & (
        history["date"] >= as_of - pd.Timedelta(days=27))
    thinned = history[~recent]
    assert MIN_RECENT_OBS > 1

    out = forecast_from_series(model, thinned, as_of.date())

    assert (victim, 1) not in out                       # falls back to today's quote
    assert any(m != victim for m, _ in out)             # others are unaffected


def test_an_implausible_forecast_is_discarded(trained, monkeypatch):
    model, series = trained
    as_of = _as_of_with_reporters(series)

    def crazy(df, h):
        p = np.exp(df["logp"].to_numpy())
        return pd.DataFrame({"p10": p * 5, "p50": p * 8, "p90": p * 12}, index=df.index)

    monkeypatch.setattr(model, "predict_prices", crazy)
    assert forecast_from_series(model, series[series["date"] <= as_of], as_of.date()) == {}


def test_nothing_to_forecast_returns_empty_instead_of_raising(trained):
    model, series = trained
    assert forecast_from_series(model, series.iloc[0:0], pd.Timestamp("2023-06-01").date()) == {}
    # a day on which nobody reported
    assert forecast_from_series(model, series, pd.Timestamp("2010-01-01").date()) == {}


def test_states_and_commodities_the_model_never_saw_get_no_forecast(trained):
    """Trained on StateA/StateB tomato; asking about an unseen state or commodity must not guess."""
    model, series = trained
    as_of = _as_of_with_reporters(series)
    history = series[series["date"] <= as_of]
    assert forecast_from_series(model, history, as_of.date())      # sanity: normally works

    other_state = history.assign(state="Atlantis")
    assert forecast_from_series(model, other_state, as_of.date()) == {}

    other_commodity = history.assign(commodity="Brinjal")
    assert forecast_from_series(model, other_commodity, as_of.date()) == {}


def test_a_missing_model_file_means_no_forecaster_not_a_crash(tmp_path):
    get_forecaster.cache_clear()
    assert get_forecaster(str(tmp_path / "does_not_exist.pkl")) is None
    get_forecaster.cache_clear()
