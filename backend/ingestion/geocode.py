"""Nominatim geocoder for mandi locations.

Mandis don't move — geocode once, cache forever. The CSV cache
(`data/reference/mandi_geocodes.csv`) is versioned so results survive DB
rebuilds and are diffable in review.

Nominatim usage policy (public server):
- Max 1 request per second (we enforce ≥ 1.1s).
- User-Agent header identifying the application + contact.
- Cache results locally; never batch-hammer.

If we ever exceed the fair-use budget, self-hosting Nominatim from the same
India OSM extract used by OSRM (Phase 2 §2.4) is a drop-in replacement —
change `NOMINATIM_BASE_URL` to the self-hosted endpoint.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog
from sqlalchemy import text
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.db.connection import get_engine

log = structlog.get_logger(__name__)

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "FreshRoute/0.1 (IIIT Una capstone; contact via GitHub issue)"
MIN_INTERVAL_SEC = 1.1

CACHE_PATH = Path("data/reference/mandi_geocodes.csv")
CACHE_COLUMNS = [
    "market_id", "state", "district", "market",
    "latitude", "longitude", "source", "raw_display_name",
]


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    display_name: str


class GeocodeMiss(RuntimeError):
    """Nominatim returned zero results for the query. Not an error — logged
    and skipped, and the mandi can be geocoded manually later."""


def _load_cache() -> dict[int, dict[str, str]]:
    if not CACHE_PATH.exists():
        return {}
    out: dict[int, dict[str, str]] = {}
    with CACHE_PATH.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            out[int(row["market_id"])] = row
    return out


def _write_cache(rows: list[dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CACHE_COLUMNS)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: int(r["market_id"])):
            writer.writerow(row)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError,)),
)
def _query_nominatim(query: str, country: str = "India") -> GeocodeResult:
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "addressdetails": 0,
    }
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(base_url=NOMINATIM_BASE_URL, timeout=30) as client:
        resp = client.get("/search", params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if not data:
        raise GeocodeMiss(query)
    top = data[0]
    return GeocodeResult(
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
        display_name=top.get("display_name", ""),
    )


def _query_variants(market: str, district: str, state: str) -> list[str]:
    """Try a few plausible query forms — Nominatim is finicky about mandi names."""
    market = market.strip()
    district = district.strip()
    state = state.strip()
    variants = [
        f"{market} mandi, {district}, {state}, India",
        f"{market}, {district}, {state}, India",
        f"{market} APMC, {district}, {state}, India",
        f"{market}, {state}, India",
    ]
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _fetch_markets() -> list[dict]:
    sql = text(
        """
        SELECT m.id AS market_id, m.district, m.name AS market,
               s.name AS state, m.latitude, m.longitude
        FROM markets m
        JOIN states s ON s.id = m.state_id
        WHERE m.is_active = TRUE
        ORDER BY s.name, m.district, m.name
        """
    )
    with get_engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql).all()]


def _update_market(market_id: int, lat: float, lon: float, source: str) -> None:
    sql = text(
        """
        UPDATE markets
        SET latitude = :lat, longitude = :lon, geocode_source = :src
        WHERE id = :id
        """
    )
    with get_engine().begin() as conn:
        conn.execute(sql, {"id": market_id, "lat": lat, "lon": lon, "src": source})


def geocode_all(force: bool = False) -> dict[str, int]:
    """Geocode every active mandi that isn't already resolved.

    Returns a summary: {resolved, cached, missed, skipped}.
    - `resolved` — new hits from Nominatim this run
    - `cached`   — served from the CSV cache
    - `missed`   — Nominatim returned no result
    - `skipped`  — already had lat/lon in DB and `force=False`
    """
    markets = _fetch_markets()
    cache = _load_cache()
    stats = {"resolved": 0, "cached": 0, "missed": 0, "skipped": 0}
    last_call = 0.0

    updated_cache = dict(cache)

    for market in markets:
        mid = int(market["market_id"])
        has_coords = market["latitude"] is not None and market["longitude"] is not None
        if has_coords and not force:
            stats["skipped"] += 1
            continue

        cached = cache.get(mid)
        if cached and cached.get("latitude") and cached.get("longitude") and not force:
            _update_market(
                mid,
                float(cached["latitude"]),
                float(cached["longitude"]),
                cached.get("source") or "nominatim",
            )
            stats["cached"] += 1
            continue

        # Rate limit — hard-enforced across the whole loop.
        elapsed = time.monotonic() - last_call
        if elapsed < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - elapsed)

        result: GeocodeResult | None = None
        for query in _query_variants(market["market"], market["district"] or "", market["state"]):
            try:
                result = _query_nominatim(query)
                last_call = time.monotonic()
                break
            except GeocodeMiss:
                last_call = time.monotonic()
                continue
            except httpx.HTTPError as exc:
                last_call = time.monotonic()
                log.warning("geocode_http_error", market_id=mid, query=query, error=str(exc))
                continue

        if result is None:
            stats["missed"] += 1
            log.warning("geocode_missed", market_id=mid, market=market["market"])
            continue

        _update_market(mid, result.latitude, result.longitude, "nominatim")
        updated_cache[mid] = {
            "market_id": str(mid),
            "state": market["state"],
            "district": market["district"] or "",
            "market": market["market"],
            "latitude": f"{result.latitude:.6f}",
            "longitude": f"{result.longitude:.6f}",
            "source": "nominatim",
            "raw_display_name": result.display_name,
        }
        stats["resolved"] += 1
        log.info("geocode_ok", market_id=mid, market=market["market"], lat=result.latitude, lon=result.longitude)

    _write_cache(list(updated_cache.values()))
    log.info("geocode_summary", **stats)
    return stats
