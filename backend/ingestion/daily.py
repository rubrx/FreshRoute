"""Incremental daily pull.

Pulls the last N days (default 7) for a given (state, commodity) set so we
catch late-reporting mandis. Idempotent thanks to the natural-key upsert.
"""

from __future__ import annotations

from datetime import date, timedelta

import structlog

from backend.db.connection import session_scope
from backend.ingestion.agmarknet_client import FetchRequest, fetch
from backend.ingestion.normalize import normalize
from backend.ingestion.upsert import upsert_panel

log = structlog.get_logger(__name__)


def daily_pull(
    states: list[str],
    commodities: list[str],
    lookback_days: int = 7,
) -> dict[str, int]:
    """Fetch the last `lookback_days` for each (state, commodity)."""
    today = date.today()
    start = today - timedelta(days=lookback_days)

    results: dict[str, int] = {}
    for st in states:
        for cm in commodities:
            key = f"{st}::{cm}"
            raw = fetch(FetchRequest(state=st, commodity=cm, from_date=start, to_date=today))
            normalized = normalize(raw)
            rows = 0
            if not normalized.empty:
                with session_scope() as session:
                    rows = upsert_panel(session, normalized, source="agmarknet")
            results[key] = rows
            log.info("daily_pull_pair", state=st, commodity=cm, rows=rows)
    return results
