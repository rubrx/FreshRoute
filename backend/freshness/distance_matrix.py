"""OSRM-backed distance matrix for mandi pairs.

Uses the self-hosted OSRM instance (see `docker-compose.yml` and
`scripts/osrm_bootstrap.sh`). Caches results to
`data/processed/distance_matrix.parquet` so we never re-hit OSRM for the
same pair.

The full 100×100 pairwise matrix is ~10k routes. OSRM's `table` service can
return the whole thing in one call, but we use the `route` service per pair
so we also get the encoded polyline — the Phase 4 freshness engine needs
the polyline to sample temperature along it.

Storage columns (parquet):
- origin_id, origin_lat, origin_lon
- dest_id,   dest_lat,   dest_lon
- distance_km, duration_hours
- polyline_geojson   (JSON-encoded LineString, may be None if the caller
                     opted out to save space)
- computed_at        (UTC ISO timestamp)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
import structlog
from sqlalchemy import text
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings
from backend.db.connection import get_engine

log = structlog.get_logger(__name__)

MATRIX_PATH = Path("data/processed/distance_matrix.parquet")
MATRIX_COLUMNS = [
    "origin_id", "origin_lat", "origin_lon",
    "dest_id",   "dest_lat",   "dest_lon",
    "distance_km", "duration_hours",
    "polyline_geojson", "computed_at",
]


@dataclass(frozen=True)
class RoutePair:
    origin_id: int
    origin_lat: float
    origin_lon: float
    dest_id: int
    dest_lat: float
    dest_lon: float


class OsrmError(RuntimeError):
    pass


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.HTTPError, OsrmError)),
)
def _query_osrm(pair: RoutePair, include_polyline: bool) -> dict:
    """Call OSRM /route/v1/driving. Returns the first route object."""
    settings = get_settings()
    coords = (
        f"{pair.origin_lon},{pair.origin_lat};"
        f"{pair.dest_lon},{pair.dest_lat}"
    )
    params = {
        "overview": "full" if include_polyline else "false",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    }
    url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{coords}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise OsrmError(f"OSRM returned {data.get('code')}: {data.get('message', 'no message')}")

    return data["routes"][0]


def _load_cache() -> pd.DataFrame:
    if MATRIX_PATH.exists():
        return pd.read_parquet(MATRIX_PATH)
    return pd.DataFrame(columns=MATRIX_COLUMNS)


def _save_cache(df: pd.DataFrame) -> None:
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(MATRIX_PATH, index=False)


def _fetch_geocoded_markets(market_ids: list[int] | None = None) -> pd.DataFrame:
    """Load geocoded active mandis. If `market_ids` is given, restrict to them."""
    if market_ids:
        sql = text(
            """
            SELECT id AS market_id, latitude, longitude
            FROM markets
            WHERE is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND id = ANY(:ids)
            """
        )
        params = {"ids": market_ids}
    else:
        sql = text(
            """
            SELECT id AS market_id, latitude, longitude
            FROM markets
            WHERE is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        )
        params = {}
    return pd.read_sql(sql, get_engine(), params=params)


def build_pairs(
    origin_ids: list[int] | None = None,
    dest_ids: list[int] | None = None,
) -> list[RoutePair]:
    """Cross-product of origins × destinations (excluding self-pairs).

    If both lists are None, uses every geocoded active mandi for both sides
    → full pairwise matrix. For a realistic trader use-case, pass a small
    origin list (their local mandis) and let dest be all mandis.
    """
    all_ids = list({*(origin_ids or []), *(dest_ids or [])}) or None
    df = _fetch_geocoded_markets(all_ids)
    if df.empty:
        return []
    by_id = {int(r.market_id): (float(r.latitude), float(r.longitude)) for r in df.itertuples(index=False)}

    def _resolve(ids: list[int] | None) -> list[int]:
        return list(by_id.keys()) if ids is None else [i for i in ids if i in by_id]

    origins = _resolve(origin_ids)
    dests = _resolve(dest_ids)

    pairs: list[RoutePair] = []
    for o in origins:
        for d in dests:
            if o == d:
                continue
            o_lat, o_lon = by_id[o]
            d_lat, d_lon = by_id[d]
            pairs.append(RoutePair(o, o_lat, o_lon, d, d_lat, d_lon))
    return pairs


def compute_matrix(
    origin_ids: list[int] | None = None,
    dest_ids: list[int] | None = None,
    include_polyline: bool = True,
    force: bool = False,
) -> pd.DataFrame:
    """Compute (or refresh) distance/duration for the given pair set.

    Cached pairs are skipped unless `force=True`. Cache is rewritten in-place
    at the end of the run.
    """
    pairs = build_pairs(origin_ids=origin_ids, dest_ids=dest_ids)
    if not pairs:
        log.warning("distance_matrix_no_pairs")
        return pd.DataFrame(columns=MATRIX_COLUMNS)

    cache = _load_cache()
    cache_keys = set(zip(cache["origin_id"].astype(int), cache["dest_id"].astype(int))) if not cache.empty else set()

    new_rows: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for pair in pairs:
        if not force and (pair.origin_id, pair.dest_id) in cache_keys:
            continue
        try:
            route = _query_osrm(pair, include_polyline=include_polyline)
        except (httpx.HTTPError, OsrmError) as exc:
            log.warning(
                "distance_matrix_pair_failed",
                origin=pair.origin_id, dest=pair.dest_id, error=str(exc),
            )
            continue

        polyline = json.dumps(route["geometry"]) if include_polyline and "geometry" in route else None
        new_rows.append({
            "origin_id":       pair.origin_id,
            "origin_lat":      pair.origin_lat,
            "origin_lon":      pair.origin_lon,
            "dest_id":         pair.dest_id,
            "dest_lat":        pair.dest_lat,
            "dest_lon":        pair.dest_lon,
            "distance_km":     route["distance"] / 1000.0,
            "duration_hours":  route["duration"] / 3600.0,
            "polyline_geojson": polyline,
            "computed_at":     now,
        })

    if not new_rows:
        log.info("distance_matrix_nothing_new", cached=len(cache))
        return cache

    new_df = pd.DataFrame(new_rows, columns=MATRIX_COLUMNS)
    if force and not cache.empty:
        # Drop the pairs we just recomputed so the update replaces cleanly.
        mask = ~cache.set_index(["origin_id", "dest_id"]).index.isin(
            new_df.set_index(["origin_id", "dest_id"]).index
        )
        cache = cache[mask]
    merged = pd.concat([cache, new_df], ignore_index=True)
    _save_cache(merged)
    log.info(
        "distance_matrix_updated",
        new_pairs=len(new_df),
        total_pairs=len(merged),
    )
    return merged


def load_matrix() -> pd.DataFrame:
    """Public read-only accessor for the cached matrix."""
    return _load_cache()
