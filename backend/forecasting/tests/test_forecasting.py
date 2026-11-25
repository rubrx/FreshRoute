"""Tests for the price forecaster: data cleaning, leak-free features, baselines, model, backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.forecasting.backtest import (
    pinball,
    run_backtest,
    score,
    split_for_fold,
    summarize,
    write_report,
)
from backend.forecasting.baselines import EmpiricalReturnBaseline, add_baseline_columns
from backend.forecasting.features import FEATURES, make_dataset
from backend.forecasting.model import Forecaster
from backend.forecasting.panel import clean_series


# ---------------------------------------------------------------- synthetic data
def synthetic_panel(seed: int = 0, years: int = 5, markets_per_state: int = 4,
                    report_prob: float = 0.7, phi: float = 0.5, noise: float = 0.08) -> pd.DataFrame:
    """Seasonal log prices + a mean-reverting (AR1) market-specific deviation, reported sparsely."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=365 * years, freq="D")
    doy = dates.dayofyear.to_numpy()
    rows, market_id = [], 0
    for state in ("StateA", "StateB"):
        for commodity in ("Tomato", "Onion"):
            for _ in range(markets_per_state):
                market_id += 1
                x = np.zeros(len(dates))
                for t in range(1, len(dates)):
                    x[t] = phi * x[t - 1] + rng.normal(0, noise)
                logp = 7.5 + 0.25 * np.sin(2 * np.pi * doy / 365.25) + rng.normal(0, 0.2) + x
                reported = rng.random(len(dates)) < report_prob
                for d, lp in zip(dates[reported], logp[reported], strict=True):
                    p = float(np.exp(lp))
                    rows.append((d, market_id, state, "D", f"M{market_id}", commodity, "",
                                 p * 0.9, p, p * 1.1, np.nan, "test"))
    return pd.DataFrame(rows, columns=[
        "date", "market_id", "state", "district", "market", "commodity", "variety",
        "min_price", "modal_price", "max_price", "arrival_tonnes", "source"])


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return synthetic_panel()


@pytest.fixture(scope="module")
def series(panel) -> pd.DataFrame:
    return clean_series(panel)


@pytest.fixture(scope="module")
def dataset(series):
    return make_dataset(series)


# ------------------------------------------------------------------- cleaning
def test_clean_series_takes_the_median_across_varieties_and_drops_typos():
    days = pd.date_range("2024-01-01", periods=20, freq="D")
    rows = [(d, 1, "S", "D", "M", "Tomato", "A", 90, 100.0, 110, np.nan, "x") for d in days]
    rows.append((days[3], 1, "S", "D", "M", "Tomato", "B", 190, 200.0, 210, np.nan, "x"))  # 2nd variety
    rows[10] = (days[10], 1, "S", "D", "M", "Tomato", "A", 900, 1000.0, 1100, np.nan, "x")   # 10x typo
    rows.append((days[12], 1, "S", "D", "M", "Tomato", "A", 0, 0.0, 0, np.nan, "x"))        # zero price
    panel = pd.DataFrame(rows, columns=[
        "date", "market_id", "state", "district", "market", "commodity", "variety",
        "min_price", "modal_price", "max_price", "arrival_tonnes", "source"])

    out = clean_series(panel)

    assert days[10] not in set(out["date"])                          # typo gone
    assert out.loc[out["date"] == days[3], "modal"].iloc[0] == 150.0  # median of 100 and 200
    assert (out["modal"] > 0).all()
    assert out["date"].is_unique


# ------------------------------------------------------------------- features
def test_features_never_look_ahead(series):
    """Changing prices AFTER day T must not change any feature on or before day T."""
    cutoff = pd.Timestamp("2022-06-30")
    changed = series.copy()
    future = changed["date"] > cutoff
    changed.loc[future, "modal"] = changed.loc[future, "modal"] * 1.7
    changed.loc[future, ["pmin", "pmax"]] = changed.loc[future, ["pmin", "pmax"]].to_numpy() * 1.7

    a, enc = make_dataset(series)
    b, _ = make_dataset(changed, enc=enc)
    key = ["market_id", "commodity", "date"]
    a = a[a["date"] <= cutoff].set_index(key).sort_index()
    b = b[b["date"] <= cutoff].set_index(key).sort_index()

    assert a.index.equals(b.index)
    for col in FEATURES:
        np.testing.assert_allclose(a[col].to_numpy(float), b[col].to_numpy(float),
                                   equal_nan=True, err_msg=f"feature {col} leaks the future")


def test_target_is_the_future_log_price_change(series, dataset):
    ds, _ = dataset
    s = series.set_index(["market_id", "commodity", "date"])["modal"]
    checked = 0
    for r in ds.sample(300, random_state=1).itertuples():
        nxt = (r.market_id, r.commodity, r.date + pd.Timedelta(days=1))
        if nxt in s.index:
            assert r.y1 == pytest.approx(np.log(s[nxt]) - r.logp)
            checked += 1
        else:
            assert np.isnan(r.y1)       # no report tomorrow -> no target, nothing is filled in
            checked += 1
    assert checked == 300


def test_dataset_rows_are_days_the_mandi_reported(series, dataset):
    ds, _ = dataset
    assert (ds["age"] == 0).all()
    assert len(ds) <= len(series)


# ------------------------------------------------------------------- baselines
def test_pinball_matches_a_hand_calculation():
    y = np.array([1.0, 2.0])
    q = np.array([0.0, 3.0])
    # tau=0.9: err=+1 -> 0.9*1 ; err=-1 -> (0.9-1)*(-1)=0.1 ; mean 0.5
    assert pinball(y, q, 0.9) == pytest.approx(0.5)


def test_empirical_baseline_is_roughly_calibrated():
    rng = np.random.default_rng(3)
    n = 20000
    df = pd.DataFrame({"commodity": "Tomato", "logp": 7.0, "dev7": 0.0,
                       "y1": rng.normal(0, 0.05, n)})
    df = add_baseline_columns(df)
    b = EmpiricalReturnBaseline("logp", 1).fit(df.iloc[:10000])
    q = b.predict(df.iloc[10000:])
    y = df["y1"].iloc[10000:].to_numpy()
    assert np.mean((y >= q[:, 0]) & (y <= q[:, 2])) == pytest.approx(0.8, abs=0.03)


# ----------------------------------------------------------------------- model
def test_split_never_trains_on_targets_from_the_test_period(dataset):
    ds, _ = dataset
    start, end = pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31")
    for h in (1, 3):
        train, test = split_for_fold(ds, h, start, end)
        assert (train["date"] + pd.Timedelta(days=h) < start).all()
        assert test["date"].between(start, end).all()
        assert len(train) > 0 and len(test) > 0


def test_model_beats_naive_when_prices_mean_revert(dataset):
    ds, enc = dataset
    ds = add_baseline_columns(ds)
    train, test = split_for_fold(ds, 1, pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"))
    model = Forecaster.fit(train, enc, horizons=(1,), rounds=120)
    y, price = test["y1"].to_numpy(), test["price"].to_numpy()

    lgbm = score(y, model.predict(test, 1), price)
    naive = score(y, EmpiricalReturnBaseline("logp", 1).fit(train).predict(test), price)

    assert lgbm["pinball"] < naive["pinball"]
    assert 0.6 < lgbm["coverage"] < 0.95


def test_predicted_quantiles_are_ordered_and_survive_save_and_load(dataset, tmp_path):
    ds, enc = dataset
    train, test = split_for_fold(ds, 2, pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"))
    model = Forecaster.fit(train, enc, horizons=(2,), rounds=40)

    q = model.predict(test, 2)
    assert (np.diff(q, axis=1) >= 0).all()           # P10 <= P50 <= P90 on every row

    prices = model.predict_prices(test, 2)
    assert list(prices.columns) == ["p10", "p50", "p90"]
    assert (prices["p10"] <= prices["p90"]).all()

    model.save(tmp_path / "m.pkl")
    again = Forecaster.load(tmp_path / "m.pkl")
    np.testing.assert_allclose(again.predict(test, 2), q)
    assert again.trained_through == model.trained_through


# -------------------------------------------------------------------- backtest
def test_backtest_runs_and_produces_a_report(dataset, tmp_path):
    ds, enc = dataset
    results, preds = run_backtest(ds, enc, test_years=(2022, 2023), horizons=(1,), rounds=30,
                                  min_train=1000, min_test=100)

    assert set(results["model"]) == {"lightgbm", "naive", "mean7"}
    assert set(results["year"]) == {2022, 2023}
    assert results["coverage"].between(0, 1).all()
    assert {"lightgbm_q50", "naive_q10", "y", "horizon"} <= set(preds.columns)

    summary = summarize(results)
    assert "skill_vs_naive" in summary.columns
    assert summary.loc[summary["model"] == "naive", "skill_vs_naive"].abs().max() < 1e-9

    text = write_report(results, tmp_path / "report.md", info={"rows": 123})
    assert "Summary" in text and "lightgbm" in text and (tmp_path / "report.md").exists()
