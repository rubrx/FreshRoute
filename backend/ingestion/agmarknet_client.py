"""Thin wrapper around the `agmarknet` PyPI package (v0.2.x).

The v0.2.x package exposes an `Agmarknet` client class backed by the official
REST API (not scraping). One `report(...)` call handles date-chunking and
pagination internally — so we do NOT chunk by year at this layer any more, we
just pass the requested window straight through. `backfill.py` still splits
by calendar year to keep raw parquet dumps sized reasonably.

Signature (confirmed on 0.2.2):
    from agmarknet import Agmarknet
    client = Agmarknet(request_delay=1.0)
    df = client.report(
        from_date="2024-01-01",         # ISO
        to_date="2024-01-31",
        commodity="Tomato",             # name; resolved via cached filters.json
        state="Maharashtra",
        data_type="both",               # "both" | "price" | "arrival"
    )

Returned columns include:
    arrival_date, state_name, district_name, market_name,
    cmdt_grp_name, cmdt_name, variety_name, grade_name,
    min_price, max_price, model_price, unit_name_price,
    arrival_qty, unit_name_arrival
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import pandas as pd
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

log = structlog.get_logger(__name__)


class AgmarknetError(RuntimeError):
    """Raised when the Agmarknet SDK returns something we cannot use."""


@dataclass(frozen=True)
class FetchRequest:
    state: str
    commodity: str
    from_date: date
    to_date: date
    data_type: str = "both"   # 'price' | 'arrival' | 'both'


@lru_cache(maxsize=1)
def _client():
    """Instantiate the SDK once. Cached so repeated fetches reuse the
    HTTP session + the local filters.json lookup cache."""
    try:
        from agmarknet import Agmarknet  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise AgmarknetError(
            "agmarknet package not installed. Add it to pyproject.toml deps."
        ) from exc

    settings = get_settings()
    return Agmarknet(request_delay=settings.agmarknet_request_delay_sec)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((AgmarknetError, ConnectionError, TimeoutError)),
)
def _call_sdk(req: FetchRequest) -> pd.DataFrame:
    client = _client()
    try:
        result = client.report(
            from_date=req.from_date.isoformat(),
            to_date=req.to_date.isoformat(),
            commodity=req.commodity,
            state=req.state,
            data_type=req.data_type,
        )
    except Exception as exc:
        # The SDK raises AgmarknetLookupError / AgmarknetAPIError / etc.
        # Wrap so tenacity's retry_if_exception_type sees a single family.
        raise AgmarknetError(
            f"SDK call failed for {req.commodity}/{req.state} "
            f"{req.from_date.isoformat()}..{req.to_date.isoformat()}: {exc}"
        ) from exc

    if result is None:
        raise AgmarknetError("SDK returned None")

    if not isinstance(result, pd.DataFrame):
        try:
            result = pd.DataFrame(result)
        except Exception as exc:
            raise AgmarknetError(f"Unexpected return type {type(result)!r}") from exc

    return result


def fetch(req: FetchRequest) -> pd.DataFrame:
    """Fetch one window from Agmarknet. Empty DataFrame is a valid result
    (many state/commodity/date combinations legitimately have no data)."""
    settings = get_settings()
    log.info(
        "agmarknet_fetch_start",
        state=req.state,
        commodity=req.commodity,
        from_date=req.from_date.isoformat(),
        to_date=req.to_date.isoformat(),
    )
    df = _call_sdk(req)

    # The SDK already sleeps `request_delay` before each HTTP call, but we
    # keep a small outer pause too so tight backfill loops stay polite.
    time.sleep(settings.agmarknet_request_delay_sec)

    log.info(
        "agmarknet_fetch_ok",
        state=req.state,
        commodity=req.commodity,
        rows=len(df),
    )
    return df
