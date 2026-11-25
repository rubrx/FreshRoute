"""Look-back features and look-ahead targets for per-mandi price forecasting.

Rules that keep this honest:

* Every feature at origin day ``t`` uses observations on or before ``t`` only.
* A target ``y{h}`` is ``log p(t+h) - log p(t)`` and exists only if the mandi really
  reported on day ``t+h`` (nothing is filled in on the target side).
* Training origins are days the mandi actually reported, because that is the situation
  at serving time: we hold today's reported price and want the next few days.

Mandi prices are reported sparsely (often a third of days), so every series is put on a
daily calendar, forward-filled for a limited time, and ``age`` records how stale the last
real observation is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZONS = (1, 2, 3)
LAGS = (1, 3, 7, 14, 28)
MAX_FFILL_DAYS = 30   # beyond this a mandi's last price is too stale to use at all
FRESH_DAYS = 7        # a price older than this is not used for state-level context
MIN_OBS = 30          # series with fewer observations are skipped

FEATURES = [
    "logp", "age",
    "ret1", "ret3", "ret7", "ret14", "ret28", "ret364",
    "dev7", "dev28", "sd28", "n28", "spread",
    "rel_state", "state_ret7",
    "dow", "doy_sin", "doy_cos", "month",
    "commodity_code", "state_code",
]
CATEGORICAL = ["commodity_code", "state_code"]


@dataclass
class Encoders:
    """Stable integer codes for the two categorical features (saved with the model)."""

    commodities: list[str]
    states: list[str]

    @classmethod
    def fit(cls, series: pd.DataFrame) -> Encoders:
        return cls(sorted(series["commodity"].unique()), sorted(series["state"].unique()))

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["commodity_code"] = df["commodity"].map({c: i for i, c in enumerate(self.commodities)})
        df["state_code"] = df["state"].map({s: i for i, s in enumerate(self.states)})
        # unseen categories -> -1, which LightGBM treats as missing
        df["commodity_code"] = df["commodity_code"].fillna(-1).astype("int64")
        df["state_code"] = df["state_code"].fillna(-1).astype("int64")
        return df


def _group_frame(g: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
    """Daily features/targets for ONE mandi-commodity series (columns: date, modal, pmin, pmax)."""
    g = g.sort_values("date")
    idx = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
    d = g.set_index("date")[["modal", "pmin", "pmax"]].reindex(idx)

    observed = d["modal"].notna().to_numpy()
    logp_obs = np.log(d["modal"])                       # NaN on non-reporting days
    logp = logp_obs.ffill(limit=MAX_FFILL_DAYS)         # as-of price

    pos = np.arange(len(idx), dtype=float)
    last_seen = pd.Series(np.where(observed, pos, np.nan), index=idx).ffill()
    age = pd.Series(pos, index=idx) - last_seen

    f = pd.DataFrame(index=idx)
    f["obs"] = observed
    f["logp"] = logp
    f["age"] = age
    for k in LAGS:
        f[f"ret{k}"] = logp - logp.shift(k)
    f["ret364"] = logp - logp.shift(364)

    m7 = logp_obs.rolling(7, min_periods=1).mean()
    m28 = logp_obs.rolling(28, min_periods=1).mean()
    f["dev7"] = logp - m7
    f["dev28"] = logp - m28
    f["sd28"] = logp_obs.rolling(28, min_periods=3).std()
    f["n28"] = d["modal"].notna().astype(float).rolling(28, min_periods=1).sum()
    f["spread"] = ((d["pmax"] - d["pmin"]) / d["modal"]).ffill(limit=FRESH_DAYS)

    for h in horizons:
        f[f"y{h}"] = logp_obs.shift(-h) - logp          # future: targets only
    return f


def make_dataset(
    series: pd.DataFrame,
    enc: Encoders | None = None,
    horizons: Sequence[int] = HORIZONS,
    origins_only: bool = True,
    min_obs: int = MIN_OBS,
) -> tuple[pd.DataFrame, Encoders]:
    """Build the modelling table from clean series (see `panel.clean_series`).

    Returns ``(dataset, encoders)``. With ``origins_only`` (the default) only days on which
    a mandi reported are kept, which is what training and backtesting use.
    """
    # Only series with enough history are modelled (live-only series have a few days).
    sizes = series.groupby(["market_id", "commodity"])["modal"].transform("size")
    series = series[sizes >= min_obs]
    if series.empty:
        raise ValueError("no series with enough observations to build a dataset")
    enc = enc or Encoders.fit(series)
    frames = []
    for (market_id, commodity), g in series.groupby(["market_id", "commodity"], sort=False):
        f = _group_frame(g, horizons)
        f["market_id"] = market_id
        f["commodity"] = commodity
        f["state"] = g["state"].iloc[0]
        f["market"] = g["market"].iloc[0]
        f.index.name = "date"
        frames.append(f.reset_index())
    if not frames:
        raise ValueError("no series with enough observations to build a dataset")
    big = pd.concat(frames, ignore_index=True)

    # State-level context: median price of the fresh mandis of a state on each day.
    big["_fresh"] = big["logp"].where(big["age"] <= FRESH_DAYS)
    sm = big.groupby(["state", "commodity", "date"])["_fresh"].median().rename("state_med").reset_index()
    parts = []
    for (state, commodity), s in sm.groupby(["state", "commodity"]):
        ser = s.set_index("date")["state_med"]
        ser = ser.reindex(pd.date_range(ser.index.min(), ser.index.max(), freq="D"))
        parts.append(pd.DataFrame({
            "state": state, "commodity": commodity, "date": ser.index,
            "state_med": ser.to_numpy(), "state_ret7": (ser - ser.shift(7)).to_numpy(),
        }))
    big = big.drop(columns="_fresh").merge(
        pd.concat(parts, ignore_index=True), on=["state", "commodity", "date"], how="left"
    )
    big["rel_state"] = big["logp"] - big["state_med"]

    big["dow"] = big["date"].dt.dayofweek
    big["month"] = big["date"].dt.month
    doy = big["date"].dt.dayofyear.to_numpy()
    big["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    big["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    big = enc.apply(big)
    big["price"] = np.exp(big["logp"])

    if origins_only:
        big = big[big["obs"]]
    return big.sort_values("date").reset_index(drop=True), enc
