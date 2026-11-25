"""Honest baselines for the price forecaster.

A forecaster is only worth shipping if it beats trivial rules *with the same kind of
uncertainty band*. Each baseline therefore gets empirical quantiles of its own past
errors (per commodity and horizon), fitted on the training period only. All outputs are in
the same space as the model: quantiles of ``log p(t+h) - log p(t)``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

QUANTILES = (0.1, 0.5, 0.9)

# name -> column holding the baseline's centre (a log price) in the dataset
BASELINE_CENTERS = {
    "naive": "logp",      # "tomorrow = today"
    "mean7": "m7",        # mean of the last 7 days' reported prices
}


def add_baseline_columns(ds: pd.DataFrame) -> pd.DataFrame:
    """Add the centres the baselines need (derived from existing features)."""
    ds = ds.copy()
    ds["m7"] = ds["logp"] - ds["dev7"]
    return ds


class EmpiricalReturnBaseline:
    """Centre + empirical quantiles of the log error, per commodity, for one horizon."""

    def __init__(self, center: str, horizon: int, quantiles=QUANTILES) -> None:
        self.center, self.horizon, self.quantiles = center, horizon, tuple(quantiles)
        self.table: dict[str, np.ndarray] = {}
        self.fallback = np.zeros(len(self.quantiles))

    def _residual(self, df: pd.DataFrame) -> pd.Series:
        # log p(t+h) - centre  =  y_h + logp - centre
        return df[f"y{self.horizon}"] + df["logp"] - df[self.center]

    def fit(self, train: pd.DataFrame) -> EmpiricalReturnBaseline:
        res = self._residual(train)
        ok = res.notna()
        self.fallback = np.quantile(res[ok], self.quantiles)
        for commodity, idx in train[ok].groupby("commodity").groups.items():
            if len(idx) >= 50:
                self.table[commodity] = np.quantile(res.loc[idx], self.quantiles)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """(n, len(quantiles)) quantiles of log p(t+h) - log p(t)."""
        base = (df[self.center] - df["logp"]).to_numpy()[:, None]
        resid = np.vstack([self.table.get(c, self.fallback) for c in df["commodity"]])
        return base + resid
