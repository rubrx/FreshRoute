"""data.gov.in AGMARKNET daily-price ingestion.

Resource `9ef84268-d588-465a-a308-a864a43d0070` ("Current Daily Price of
Various Commodities from Various Markets (Mandi)") is the fallback data
source after the AGMARKNET REST API started requiring per-request CAPTCHAs.
See `docs/phase1-data-source-note.md`.

Two important properties of this endpoint:

1. **Snapshot-only.** Every record has today's `arrival_date`. The resource
   does not retain history — depth accumulates only by running the daily
   pull and persisting each snapshot into `market_daily`.

2. **Prices only.** No `arrival_qty` field. `arrival_tonnes` in
   `market_daily` will be NULL for datagovin-sourced rows. The arrivals
   gap is tracked in the phase-1 data-source note and must be closed
   before the seasonal arrival index (§2.3) can be trained on real data.

Two subtleties we discovered the hard way:

- **User-Agent filtering.** Requests with the default `python-requests/*`
  UA silently time out. A `curl/*` UA returns 200 in <1s. We set a
  curl-like UA on every request.
- **Server-side filters are slow.** `filters[state]=...` reliably times
  out even though the unfiltered endpoint returns in ~2s. We pull the
  full snapshot and filter client-side.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

log = structlog.get_logger(__name__)

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
PAGE_SIZE = 1000
REQUEST_TIMEOUT_SEC = 45
CURL_UA = "curl/8.7.1"

RAW_DIR = Path("data/raw/datagovin")


class DataGovInError(RuntimeError):
    """Raised when the data.gov.in endpoint returns something unusable."""


@dataclass(frozen=True)
class SnapshotFilter:
    """Client-side filter applied after the full snapshot is pulled."""

    states: tuple[str, ...] | None = None
    commodities: tuple[str, ...] | None = None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": CURL_UA, "Accept": "*/*"})
    return s


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (DataGovInError, requests.ConnectionError, requests.Timeout)
    ),
)
def _fetch_page(session: requests.Session, api_key: str, offset: int) -> dict:
    r = session.get(
        BASE_URL,
        params={
            "api-key": api_key,
            "format": "json",
            "limit": PAGE_SIZE,
            "offset": offset,
        },
        timeout=REQUEST_TIMEOUT_SEC,
    )
    if r.status_code != 200:
        raise DataGovInError(
            f"data.gov.in returned {r.status_code} at offset={offset}: {r.text[:200]}"
        )
    try:
        return r.json()
    except ValueError as exc:
        raise DataGovInError(f"non-JSON response at offset={offset}") from exc


def fetch_snapshot(api_key: str | None = None) -> pd.DataFrame:
    """Pull the full current-day snapshot as one DataFrame.

    Returns a DataFrame with the raw data.gov.in columns. Downstream
    `normalize()` handles renaming.
    """
    settings = get_settings()
    key = api_key or settings.data_gov_in_api_key
    if not key:
        raise DataGovInError(
            "DATA_GOV_IN_API_KEY not set. Register at data.gov.in and add it to .env."
        )

    session = _session()
    all_records: list[dict] = []
    offset = 0
    t0 = time.time()

    while True:
        data = _fetch_page(session, key, offset)
        records = data.get("records", []) or []
        total = data.get("total")
        all_records.extend(records)
        log.info(
            "datagovin_page_ok",
            offset=offset,
            page_rows=len(records),
            cumulative=len(all_records),
            total=total,
        )
        if len(records) < PAGE_SIZE:
            break
        if total is not None and len(all_records) >= total:
            break
        offset += PAGE_SIZE
        # Polite pause between pages so we do not hammer the endpoint.
        time.sleep(0.5)

    log.info(
        "datagovin_snapshot_ok",
        rows=len(all_records),
        elapsed_sec=round(time.time() - t0, 2),
    )
    return pd.DataFrame(all_records)


def apply_filter(df: pd.DataFrame, flt: SnapshotFilter) -> pd.DataFrame:
    """Filter the raw snapshot by state and/or commodity, case-insensitive."""
    if df.empty:
        return df
    out = df
    if flt.states:
        wanted = {s.strip().casefold() for s in flt.states}
        out = out[out["state"].fillna("").str.strip().str.casefold().isin(wanted)]
    if flt.commodities:
        wanted = {c.strip().casefold() for c in flt.commodities}
        out = out[out["commodity"].fillna("").str.strip().str.casefold().isin(wanted)]
    return out.reset_index(drop=True)


def dump_raw(df: pd.DataFrame, snapshot_date: date | None = None) -> Path:
    """Persist the raw snapshot as parquet under data/raw/datagovin/."""
    if df.empty:
        raise DataGovInError("refusing to dump an empty snapshot")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    d = snapshot_date or date.today()
    path = RAW_DIR / f"snapshot_{d.isoformat()}.parquet"
    df.to_parquet(path, index=False)
    log.info("datagovin_raw_dumped", path=str(path), rows=len(df))
    return path
