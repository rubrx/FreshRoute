"""Historical backfill from Agmarknet, chunked by year, resumable.

Progress is tracked in `data/raw/agmarknet/state.json` keyed by (state, commodity).
Rerunning `backfill` picks up where the last run left off.

Also lands the raw normalized DataFrame to
`data/raw/agmarknet/{year}/{state}/{commodity}.parquet` for offline analysis.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import structlog

from backend.db.connection import session_scope
from backend.ingestion.agmarknet_client import FetchRequest, fetch
from backend.ingestion.normalize import normalize
from backend.ingestion.upsert import upsert_panel

log = structlog.get_logger(__name__)

RAW_ROOT = Path("data/raw/agmarknet")
STATE_FILE = RAW_ROOT / "state.json"

DEFAULT_START = date(2007, 1, 1)


def _load_state() -> dict[str, str]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _key(state: str, commodity: str) -> str:
    return f"{state}::{commodity}"


def _year_range(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into per-year (from, to) chunks."""
    chunks: list[tuple[date, date]] = []
    y = start.year
    while y <= end.year:
        chunk_start = max(date(y, 1, 1), start)
        chunk_end = min(date(y, 12, 31), end)
        chunks.append((chunk_start, chunk_end))
        y += 1
    return chunks


def _write_raw_parquet(df, year: int, state: str, commodity: str) -> None:
    if df.empty:
        return
    out_dir = RAW_ROOT / str(year) / state.replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{commodity.replace(' ', '_')}.parquet"
    df.to_parquet(out_path, index=False)


def backfill_pair(
    state: str,
    commodity: str,
    start: date = DEFAULT_START,
    end: date | None = None,
) -> int:
    """Backfill one (state, commodity) pair. Returns rows written across all chunks."""
    end = end or date.today()

    progress = _load_state()
    resume_from_iso = progress.get(_key(state, commodity))
    if resume_from_iso:
        resume_from = date.fromisoformat(resume_from_iso)
        if resume_from > start:
            log.info(
                "backfill_resume",
                state=state,
                commodity=commodity,
                resume_from=resume_from.isoformat(),
            )
            start = resume_from

    total = 0
    for chunk_start, chunk_end in _year_range(start, end):
        req = FetchRequest(
            state=state,
            commodity=commodity,
            from_date=chunk_start,
            to_date=chunk_end,
            data_type="both",
        )
        raw = fetch(req)
        normalized = normalize(raw)
        _write_raw_parquet(normalized, chunk_start.year, state, commodity)

        if not normalized.empty:
            with session_scope() as session:
                total += upsert_panel(session, normalized, source="agmarknet")

        # Advance the cursor to the day after this chunk. Even empty chunks
        # count as processed so we don't re-fetch them on the next run.
        progress[_key(state, commodity)] = (chunk_end).isoformat()
        _save_state(progress)

    log.info("backfill_pair_done", state=state, commodity=commodity, rows=total)
    return total


def backfill_matrix(
    states: list[str],
    commodities: list[str],
    start: date = DEFAULT_START,
    end: date | None = None,
) -> dict[str, int]:
    """Backfill the full cartesian product. Returns rows-written per pair."""
    results: dict[str, int] = {}
    for st in states:
        for cm in commodities:
            results[_key(st, cm)] = backfill_pair(st, cm, start=start, end=end)
    return results
