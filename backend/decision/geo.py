"""Geographic helpers for the recommender.

Because OSRM has not been provisioned in the demo environment (no
mandi geocodes populated, no road-distance matrix), the recommender
uses straight-line haversine distance between the origin and either
the destination district centroid (preferred) or the destination
state centroid (fallback).

Every response tags distance as ``approximate`` when a state centroid
is used, so a farmer/trader is never misled into thinking the
kilometres shown are road-precise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

REFERENCE_DIR = Path(__file__).parent.parent.parent / "data" / "reference"
STATE_CENTROIDS_CSV = REFERENCE_DIR / "state_centroids.csv"
DISTRICT_CENTROIDS_CSV = REFERENCE_DIR / "district_centroids.csv"

EARTH_RADIUS_KM = 6371.0088

# Straight-line distance is systematically shorter than road distance;
# this factor lifts the haversine to a rough road-distance estimate.
# 1.30 is the commonly cited detour ratio for India inter-district
# state highways. Kept explicit so the audit can see it.
ROAD_DETOUR_FACTOR = 1.30


@dataclass(frozen=True)
class Centroid:
    latitude: float
    longitude: float
    source: str  # "district" | "state"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lon pairs."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def estimated_road_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine × detour factor — a rough road-distance estimate.

    Preferred over raw haversine so downstream cost/spoilage math is not
    silently optimistic. Still labelled ``estimated`` in the response.
    """
    return round(haversine_km(lat1, lon1, lat2, lon2) * ROAD_DETOUR_FACTOR, 1)


@lru_cache
def _state_centroids() -> dict[str, tuple[float, float]]:
    df = pd.read_csv(STATE_CENTROIDS_CSV)
    return {r.state: (float(r.latitude), float(r.longitude)) for r in df.itertuples(index=False)}


@lru_cache
def _district_centroids() -> dict[tuple[str, str], tuple[float, float]]:
    df = pd.read_csv(DISTRICT_CENTROIDS_CSV)
    out: dict[tuple[str, str], tuple[float, float]] = {}
    for r in df.itertuples(index=False):
        out[(r.state, r.district)] = (float(r.latitude), float(r.longitude))
    return out


def resolve_centroid(state: str, district: str | None) -> Centroid | None:
    """District centroid if we have one; otherwise state centroid; otherwise None."""
    if district:
        hit = _district_centroids().get((state, district))
        if hit is not None:
            return Centroid(latitude=hit[0], longitude=hit[1], source="district")
    state_hit = _state_centroids().get(state)
    if state_hit is not None:
        return Centroid(latitude=state_hit[0], longitude=state_hit[1], source="state")
    return None
