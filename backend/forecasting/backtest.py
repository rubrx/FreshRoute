"""Rolling-origin backtest of the quantile forecaster against honest baselines.

Each fold trains on everything that was knowable before a test year starts and is scored on
that year. A training row for horizon ``h`` is only used if its *target day* (``t + h``) is
also before the test period, so no information from the test year leaks into training.

Metrics (all on held-out rows):
* ``pinball``   mean pinball loss over P10/P50/P90, on the log-return scale (lower is better)
* ``mae_rs``    mean absolute error of the P50 price, Rs per quintal
* ``mape``      the same as a fraction of the actual price
* ``coverage``  share of actuals inside [P10, P90] (a calibrated model gives about 0.80)
* ``width``     mean width of [P10, P90] as a fraction of today's price
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from backend.forecasting.baselines import (
    BASELINE_CENTERS,
    EmpiricalReturnBaseline,
    add_baseline_columns,
)
from backend.forecasting.features import HORIZONS, Encoders
from backend.forecasting.model import DEFAULT_ROUNDS, QUANTILES, Forecaster

log = structlog.get_logger(__name__)

RESULTS_PATH = Path("data/processed/backtest_results.csv")
PREDICTIONS_PATH = Path("data/processed/backtest_predictions.parquet")
REPORT_PATH = Path("docs/forecast-backtest.md")


# ------------------------------------------------------------------ metrics
def pinball(y: np.ndarray, q: np.ndarray, tau: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1.0) * d)))


def score(y: np.ndarray, qpred: np.ndarray, price: np.ndarray,
          quantiles: Sequence[float] = QUANTILES) -> dict:
    """Metrics for one model on one fold/horizon. ``qpred`` columns follow ``quantiles``."""
    quantiles = tuple(quantiles)
    pin = float(np.mean([pinball(y, qpred[:, i], t) for i, t in enumerate(quantiles)]))
    mid = qpred[:, quantiles.index(0.5)]
    actual, hat = price * np.exp(y), price * np.exp(mid)
    lo, hi = qpred[:, 0], qpred[:, -1]
    return {
        "n": int(len(y)),
        "pinball": pin,
        "mae_rs": float(np.mean(np.abs(hat - actual))),
        "mape": float(np.mean(np.abs(hat - actual) / actual)),
        "coverage": float(np.mean((y >= lo) & (y <= hi))),
        "width": float(np.mean(np.exp(hi) - np.exp(lo))),
    }


# -------------------------------------------------------------------- folds
def split_for_fold(ds: pd.DataFrame, h: int, test_start: pd.Timestamp,
                   test_end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train/test rows for horizon ``h``; training targets must resolve before ``test_start``."""
    valid = ds[ds[f"y{h}"].notna()]
    target_day = valid["date"] + pd.Timedelta(days=h)
    train = valid[target_day < test_start]
    test = valid[(valid["date"] >= test_start) & (valid["date"] <= test_end)]
    return train, test


def run_backtest(
    ds: pd.DataFrame,
    enc: Encoders,
    test_years: Sequence[int] = (2022, 2023, 2024, 2025),
    horizons: Sequence[int] = HORIZONS,
    rounds: int = DEFAULT_ROUNDS,
    min_train: int = 2000,
    min_test: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns ``(results, predictions)``; results has one row per year x horizon x model."""
    ds = add_baseline_columns(ds)
    rows: list[dict] = []
    pred_frames: list[pd.DataFrame] = []

    for year in test_years:
        start, end = pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31)
        for h in horizons:
            train, test = split_for_fold(ds, h, start, end)
            if len(train) < min_train or len(test) < min_test:
                log.warning("backtest_fold_skipped", year=year, horizon=h,
                            train=len(train), test=len(test))
                continue

            model = Forecaster.fit(train, enc, horizons=(h,), rounds=rounds)
            sets = {"lightgbm": model.predict(test, h)}
            for name, center in BASELINE_CENTERS.items():
                sets[name] = EmpiricalReturnBaseline(center, h).fit(train).predict(test)

            y = test[f"y{h}"].to_numpy()
            price = test["price"].to_numpy()
            frame = test[["date", "market_id", "market", "state", "commodity", "price"]].copy()
            frame["horizon"], frame["y"] = h, y
            for name, qp in sets.items():
                rows.append({"year": year, "horizon": h, "model": name,
                             **score(y, qp, price)})
                for i, t in enumerate(QUANTILES):
                    frame[f"{name}_q{int(t * 100)}"] = qp[:, i]
            pred_frames.append(frame)
            log.info("backtest_fold_done", year=year, horizon=h, train=len(train), test=len(test),
                     pinball_lgbm=round(rows[-3]["pinball"], 5), pinball_naive=round(rows[-2]["pinball"], 5))

    results = pd.DataFrame(rows)
    preds = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    return results, preds


# ------------------------------------------------------------------ summary
def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Fold results averaged (weighted by rows) per horizon and model, with skill vs naive."""
    def wavg(g: pd.DataFrame, col: str) -> float:
        return float(np.average(g[col], weights=g["n"]))

    out = []
    for (h, model), g in results.groupby(["horizon", "model"]):
        out.append({"horizon": h, "model": model, "n": int(g["n"].sum()),
                    **{c: wavg(g, c) for c in ("pinball", "mae_rs", "mape", "coverage", "width")}})
    s = pd.DataFrame(out)
    naive = s[s["model"] == "naive"].set_index("horizon")["pinball"]
    s["skill_vs_naive"] = 1.0 - s["pinball"] / s["horizon"].map(naive)
    order = {"lightgbm": 0, "naive": 1, "mean7": 2}
    return s.sort_values(["horizon", "model"], key=lambda c: c.map(order) if c.name == "model" else c)\
            .reset_index(drop=True)


def _md_table(df: pd.DataFrame, formats: dict[str, str]) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = [formats.get(c, "{}").format(r[c]) for c in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(results: pd.DataFrame, path: Path = REPORT_PATH, info: dict | None = None) -> str:
    summary = summarize(results)
    fmt = {"pinball": "{:.4f}", "mae_rs": "{:.0f}", "mape": "{:.1%}", "coverage": "{:.1%}",
           "width": "{:.1%}", "skill_vs_naive": "{:+.1%}", "n": "{:,}"}
    per_fold = results[["year", "horizon", "model", "n", "pinball", "mae_rs", "coverage"]]
    parts = [
        "# Price forecasting - backtest results",
        "",
        "_Generated by `python -m backend.cli forecast-backtest`; do not edit by hand._",
        "",
        "Rolling-origin evaluation: each test year is predicted by models trained only on data "
        "whose target day lies before that year. `naive` = tomorrow's price equals today's; "
        "`mean7` = mean of the last 7 reported prices; both get empirical P10/P90 bands fitted "
        "on the training period, so the comparison with LightGBM is like for like.",
        "",
    ]
    if info:
        parts += ["## Data", "", *[f"- {k}: {v}" for k, v in info.items()], ""]
    parts += [
        "## Summary (all test years, weighted by rows)", "",
        _md_table(summary, fmt), "",
        "`skill_vs_naive` is the pinball-loss improvement over the naive baseline "
        "(positive = better). `coverage` should be close to 80% for a calibrated P10-P90 band.",
        "",
        "## Per fold", "",
        _md_table(per_fold, {**fmt, "pinball": "{:.4f}"}), "",
    ]
    text = "\n".join(parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
