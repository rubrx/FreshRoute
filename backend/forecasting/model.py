"""LightGBM quantile forecaster: P10 / P50 / P90 of the price h days ahead.

One pooled model per (horizon, quantile), trained on all commodities and states with the
commodity and state as categorical features. The target is the log price change
``log p(t+h) - log p(t)``, so a predicted quantile ``q`` means a price of ``p(t) * exp(q)``.
Quantile crossing (P50 < P10 on a row) is removed by sorting each row's predictions.
"""

from __future__ import annotations

import pickle
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.forecasting.features import CATEGORICAL, FEATURES, HORIZONS, Encoders

QUANTILES = (0.1, 0.5, 0.9)
TARGET_CLIP = 1.0            # |log return| above this (~2.7x) is a data error, not a signal
MODEL_PATH = Path("data/models/forecaster.pkl")

DEFAULT_PARAMS = {
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "num_threads": 4,
    "seed": 7,
}
DEFAULT_ROUNDS = 300


@dataclass
class Forecaster:
    enc: Encoders
    horizons: tuple[int, ...] = HORIZONS
    quantiles: tuple[float, ...] = QUANTILES
    boosters: dict[tuple[int, float], lgb.Booster] = field(default_factory=dict)
    trained_through: str = ""
    notes: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ fit
    @classmethod
    def fit(
        cls,
        ds: pd.DataFrame,
        enc: Encoders,
        horizons: Sequence[int] = HORIZONS,
        quantiles: Sequence[float] = QUANTILES,
        params: dict | None = None,
        rounds: int = DEFAULT_ROUNDS,
    ) -> Forecaster:
        model = cls(enc=enc, horizons=tuple(horizons), quantiles=tuple(quantiles))
        for h in model.horizons:
            rows = ds[ds[f"y{h}"].notna()]
            if len(rows) < 500:
                raise ValueError(f"only {len(rows)} training rows for horizon {h}")
            X = rows[FEATURES]
            y = rows[f"y{h}"].clip(-TARGET_CLIP, TARGET_CLIP)
            for q in model.quantiles:
                train_set = lgb.Dataset(X, label=y, categorical_feature=CATEGORICAL)
                p = {**DEFAULT_PARAMS, **(params or {}), "objective": "quantile", "alpha": q}
                model.boosters[(h, q)] = lgb.train(p, train_set, num_boost_round=rounds)
        model.trained_through = str(pd.to_datetime(ds["date"]).max().date())
        return model

    # -------------------------------------------------------------- predict
    def predict(self, df: pd.DataFrame, h: int) -> np.ndarray:
        """(n, n_quantiles) quantiles of log p(t+h) - log p(t), sorted per row."""
        X = df[FEATURES]
        cols = [self.boosters[(h, q)].predict(X) for q in self.quantiles]
        return np.sort(np.column_stack(cols), axis=1)

    def predict_prices(self, df: pd.DataFrame, h: int) -> pd.DataFrame:
        """Same, as prices (Rs/quintal): columns p10, p50, p90."""
        q = self.predict(df, h)
        price = np.exp(df["logp"].to_numpy())[:, None]
        out = price * np.exp(q)
        return pd.DataFrame(out, index=df.index, columns=[f"p{int(x * 100)}" for x in self.quantiles])

    # ----------------------------------------------------------- persistence
    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "enc": self.enc, "horizons": self.horizons, "quantiles": self.quantiles,
            "boosters": {k: b.model_to_string() for k, b in self.boosters.items()},
            "trained_through": self.trained_through, "notes": self.notes,
            "features": FEATURES,
        }
        with open(path, "wb") as fh:
            pickle.dump(payload, fh)

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> Forecaster:
        with open(path, "rb") as fh:
            payload = pickle.load(fh)  # noqa: S301 - our own artefact, written by `save`
        if payload["features"] != FEATURES:
            raise ValueError("model was trained with a different feature set; retrain it")
        m = cls(enc=payload["enc"], horizons=tuple(payload["horizons"]),
                quantiles=tuple(payload["quantiles"]))
        m.boosters = {k: lgb.Booster(model_str=s) for k, s in payload["boosters"].items()}
        m.trained_through = payload["trained_through"]
        m.notes = payload["notes"]
        return m
