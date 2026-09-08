"""Orchestrate a data.gov.in snapshot pull into `market_daily`.

Uses `datagovin_client.fetch_snapshot()` (full snapshot, curl UA), filters
client-side by requested states/commodities, then re-uses the existing
`normalize()` + `upsert_panel()` pipeline. Sources rows as
`source='datagovin'` so we can distinguish them from any future
agmarknet-sourced backfill.
"""

from __future__ import annotations

from datetime import date

import structlog

from backend.db.connection import session_scope
from backend.ingestion.datagovin_client import (
    SnapshotFilter,
    apply_filter,
    dump_raw,
    fetch_snapshot,
)
from backend.ingestion.normalize import normalize
from backend.ingestion.upsert import upsert_panel

log = structlog.get_logger(__name__)


def pull_snapshot(
    states: list[str] | None = None,
    commodities: list[str] | None = None,
    save_raw: bool = True,
) -> dict[str, int]:
    """Pull today's data.gov.in snapshot; filter, normalize, upsert.

    Returns a summary: {'raw_rows', 'filtered_rows', 'inserted_rows'}.
    """
    raw = fetch_snapshot()
    raw_rows = len(raw)
    if raw_rows == 0:
        log.warning("datagovin_empty_snapshot")
        return {"raw_rows": 0, "filtered_rows": 0, "inserted_rows": 0}

    if save_raw:
        dump_raw(raw)

    flt = SnapshotFilter(
        states=tuple(states) if states else None,
        commodities=tuple(commodities) if commodities else None,
    )
    filtered = apply_filter(raw, flt)
    log.info(
        "datagovin_filter",
        raw_rows=raw_rows,
        filtered_rows=len(filtered),
        states=states,
        commodities=commodities,
    )

    if filtered.empty:
        return {"raw_rows": raw_rows, "filtered_rows": 0, "inserted_rows": 0}

    normalized = normalize(filtered)
    if normalized.empty:
        log.warning("datagovin_all_dropped_by_normalize", filtered_rows=len(filtered))
        return {
            "raw_rows": raw_rows,
            "filtered_rows": len(filtered),
            "inserted_rows": 0,
        }

    with session_scope() as session:
        inserted = upsert_panel(session, normalized, source="datagovin")

    log.info(
        "datagovin_pull_done",
        raw_rows=raw_rows,
        filtered_rows=len(filtered),
        inserted_rows=inserted,
        snapshot_date=date.today().isoformat(),
    )
    return {
        "raw_rows": raw_rows,
        "filtered_rows": len(filtered),
        "inserted_rows": inserted,
    }
