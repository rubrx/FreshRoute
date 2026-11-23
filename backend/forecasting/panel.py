"""Flat export of `market_daily` and clean per-mandi price series for modelling.

`export_panel` is the only DB-touching function here; everything else works on
DataFrames so it is easy to test and can run on a copy of the exported file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from sqlalchemy import text

log = structlog.get_logger(__name__)

PANEL_PATH = Path("data/processed/panel.parquet")

_EXPORT_SQL = text(
    "SELECT d.date, d.market_id, s.name AS state, COALESCE(m.district, '') AS district, "
    "m.name AS market, c.name AS commodity, d.variety, d.min_price, d.modal_price, "
    "d.max_price, d.arrival_tonnes, d.source "
    "FROM market_daily d "
    "JOIN markets m ON m.id = d.market_id "
    "JOIN states s ON s.id = m.state_id "
    "JOIN commodities c ON c.id = d.commodity_id"
)

_NUMERIC = ("min_price", "modal_price", "max_price", "arrival_tonnes")


def export_panel(path: Path = PANEL_PATH) -> pd.DataFrame:
    """Dump the whole price panel (all sources) to one parquet file."""
    from backend.db.connection import session_scope  # lazy: keeps the rest DB-free

    with session_scope() as session:
        rows = session.execute(_EXPORT_SQL).all()
    df = pd.DataFrame(
        [tuple(r) for r in rows],
        columns=["date", "market_id", "state", "district", "market", "commodity",
                 "variety", "min_price", "modal_price", "max_price", "arrival_tonnes", "source"],
    )
    df["date"] = pd.to_datetime(df["date"])
    for c in _NUMERIC:
        df[c] = df[c].astype("float64")  # NUMERIC arrives as Decimal
    df["commodity"] = df["commodity"].str.strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("panel_exported", path=str(path), rows=len(df),
             markets=df["market_id"].nunique(), first=str(df["date"].min().date()),
             last=str(df["date"].max().date()))
    return df


def clean_series(panel: pd.DataFrame, max_jump: float = 4.0, window: int = 11) -> pd.DataFrame:
    """One modal price per (market, commodity, day), with obvious data-entry errors removed.

    * several varieties on one day -> their median modal price
    * non-positive prices are dropped
    * a price more than ``max_jump`` times above/below the local median of that mandi's
      own series (centred, ``window`` observations) is treated as a typo and dropped

    Returns columns: market_id, commodity, state, district, market, date, modal, pmin, pmax.
    """
    df = panel.loc[panel["modal_price"] > 0].copy()
    if df.empty:
        return pd.DataFrame(columns=["market_id", "commodity", "state", "district", "market",
                                     "date", "modal", "pmin", "pmax"])
    out = (
        df.groupby(["market_id", "commodity", "date"], as_index=False)
        .agg(
            state=("state", "first"), district=("district", "first"), market=("market", "first"),
            modal=("modal_price", "median"), pmin=("min_price", "median"),
            pmax=("max_price", "median"),
        )
        .sort_values(["market_id", "commodity", "date"])
        .reset_index(drop=True)
    )
    local = out.groupby(["market_id", "commodity"])["modal"].transform(
        lambda s: s.rolling(window, center=True, min_periods=3).median()
    )
    ratio = out["modal"] / local
    bad = (ratio > max_jump) | (ratio < 1.0 / max_jump)
    if bad.any():
        log.info("price_outliers_dropped", rows=int(bad.sum()), of=len(out))
    out = out.loc[~bad.fillna(False)].reset_index(drop=True)
    out["market_id"] = out["market_id"].astype("int64")
    return out


def load_series(path: Path = PANEL_PATH) -> pd.DataFrame:
    """Read the exported panel and return clean per-mandi series."""
    return clean_series(pd.read_parquet(path))
