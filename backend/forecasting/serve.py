"""Serve P10/P50/P90 price forecasts to the recommender.

The recommender asks: "what will mandi X pay for this commodity when I arrive, 1-3 days
from today?". We answer from the trained `Forecaster`, using recent price history from
`market_daily`, but only when there is enough recent history to trust it. Anything else
returns no forecast and the caller falls back to today's quote.

Guard rails (a forecast that cannot be trusted is worse than none):
* the mandi must have reported on the snapshot day (that is the situation the model was
  trained for) and at least ``MIN_RECENT_OBS`` times in the last 28 days;
* a forecast more than ``MAX_PLAUSIBLE_LOG_MOVE`` away from today's price is discarded;
* the model must exist; if it does not, `get_forecaster()` returns None and nothing breaks.
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.forecasting.features import make_dataset
from backend.forecasting.model import MODEL_PATH, Forecaster
from backend.forecasting.panel import clean_series

log = structlog.get_logger(__name__)

HISTORY_DAYS = 400
MIN_RECENT_OBS = 3             # reports in the last 28 days, including the snapshot day
MAX_PLAUSIBLE_LOG_MOVE = 0.5   # ~65% away from today's price: treat as an extrapolation error
CACHE_SECONDS = 600


@dataclass(frozen=True)
class MarketForecast:
    market_id: int
    horizon_days: int
    p10: float          # Rs per quintal
    p50: float
    p90: float
    today_price: float  # the snapshot quote the forecast starts from


def horizon_days_for_hours(transit_hours: float, max_horizon: int = 3) -> int:
    """Days between 'decide today' and 'sell': a same-day trip still sells tomorrow."""
    return int(min(max(1 + transit_hours // 24, 1), max_horizon))


def forecast_from_series(
    model: Forecaster,
    series: pd.DataFrame,
    as_of: date,
    market_ids: set[int] | None = None,
) -> dict[tuple[int, int], MarketForecast]:
    """Forecasts for every mandi that reported on ``as_of`` (pure function, no database).

    ``series`` is clean per-mandi history for ONE commodity (see `panel.clean_series`).
    Returns ``{(market_id, horizon_days): MarketForecast}``.
    """
    if series.empty:
        return {}
    try:
        ds, _ = make_dataset(series, enc=model.enc, horizons=model.horizons, min_obs=1)
    except ValueError:
        return {}

    today = ds[ds["date"] == pd.Timestamp(as_of)]
    # Only states and commodities the model was trained and backtested on (unseen ones are
    # encoded as -1): extrapolating to a commodity or state it never saw would be a guess.
    today = today[(today["commodity_code"] >= 0) & (today["state_code"] >= 0)]
    if market_ids is not None:
        today = today[today["market_id"].isin(market_ids)]
    today = today[today["n28"] >= MIN_RECENT_OBS]
    if today.empty:
        return {}

    out: dict[tuple[int, int], MarketForecast] = {}
    ids = today["market_id"].to_numpy()
    price_today = np.exp(today["logp"].to_numpy())
    for h in model.horizons:
        q = model.predict_prices(today, h).to_numpy()   # columns p10, p50, p90
        for i in range(len(today)):
            p10, p50, p90 = (float(x) for x in q[i])
            if not np.isfinite([p10, p50, p90]).all() or p50 <= 0:
                continue
            if abs(np.log(p50 / price_today[i])) > MAX_PLAUSIBLE_LOG_MOVE:
                continue
            out[(int(ids[i]), h)] = MarketForecast(
                market_id=int(ids[i]), horizon_days=h, p10=p10, p50=p50, p90=p90,
                today_price=float(price_today[i]),
            )
    return out


_HISTORY_SQL = text(
    "SELECT md.date, md.market_id, s.name AS state, COALESCE(m.district, '') AS district, "
    "m.name AS market, c.name AS commodity, md.variety, md.min_price, md.modal_price, "
    "md.max_price, md.arrival_tonnes, md.source "
    "FROM market_daily md "
    "JOIN markets m ON m.id = md.market_id "
    "JOIN states s ON s.id = m.state_id "
    "JOIN commodities c ON c.id = md.commodity_id "
    "WHERE c.name = :commodity AND md.date >= :since AND md.date <= :asof "
    "AND md.modal_price IS NOT NULL"
)


def load_history(db: Session, commodity: str, as_of: date) -> pd.DataFrame:
    rows = db.execute(
        _HISTORY_SQL,
        {"commodity": commodity, "since": as_of - timedelta(days=HISTORY_DAYS), "asof": as_of},
    ).all()
    df = pd.DataFrame(
        [tuple(r) for r in rows],
        columns=["date", "market_id", "state", "district", "market", "commodity", "variety",
                 "min_price", "modal_price", "max_price", "arrival_tonnes", "source"],
    )
    df["date"] = pd.to_datetime(df["date"])
    for c in ("min_price", "modal_price", "max_price", "arrival_tonnes"):
        df[c] = df[c].astype("float64")
    return df


class PriceForecaster:
    """Loaded model + database access, with a short in-process cache per (commodity, day)."""

    def __init__(self, model: Forecaster) -> None:
        self.model = model
        self._cache: dict[tuple[str, date], tuple[float, dict]] = {}

    @property
    def trained_through(self) -> str:
        return self.model.trained_through

    def forecast(self, db: Session, commodity: str, as_of: date) -> dict[tuple[int, int], MarketForecast]:
        key = (commodity, as_of)
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
        series = clean_series(load_history(db, commodity, as_of))
        result = forecast_from_series(self.model, series, as_of)
        self._cache[key] = (time.monotonic(), result)
        log.info("forecasts_built", commodity=commodity, as_of=str(as_of),
                 mandis=len({m for m, _ in result}))
        return result


@functools.lru_cache(maxsize=1)
def get_forecaster(path: str = str(MODEL_PATH)) -> PriceForecaster | None:
    """The shared forecaster, or None if no usable model file exists (restart API after training)."""
    try:
        return PriceForecaster(Forecaster.load(Path(path)))
    except FileNotFoundError:
        log.warning("forecast_model_missing", path=path,
                    hint="run `python -m backend.cli forecast-train`")
    except Exception as exc:  # noqa: BLE001 - a bad model file must never take the API down
        log.error("forecast_model_unusable", path=path, error=str(exc)[:200])
    return None
