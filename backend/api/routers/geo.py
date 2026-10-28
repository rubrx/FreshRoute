"""Geo lookup endpoints.

Endpoints:
    GET /geo/districts?state=X  All districts for a state with lat/lon centroids.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import DistrictRow, DistrictsResponse

router = APIRouter(prefix="/geo", tags=["geo"])

_CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "reference" / "district_centroids.csv"


@lru_cache(maxsize=1)
def _load() -> dict[str, list[DistrictRow]]:
    result: dict[str, list[DistrictRow]] = {}
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            state = row["state"]
            if state not in result:
                result[state] = []
            result[state].append(
                DistrictRow(
                    district=row["district"],
                    lat=float(row["latitude"]),
                    lon=float(row["longitude"]),
                )
            )
    for districts in result.values():
        districts.sort(key=lambda d: d.district)
    return result


@router.get("/districts", response_model=DistrictsResponse)
def districts(
    state: str = Query(..., description="State name (case-sensitive, e.g. 'Uttar Pradesh')"),
) -> DistrictsResponse:
    """District name → lat/lon lookup for the GPS-fallback location picker."""
    data = _load()
    rows = data.get(state)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"No districts found for state '{state}'")
    return DistrictsResponse(state=state, count=len(rows), districts=rows)
