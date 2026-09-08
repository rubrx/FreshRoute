"""Upsert normalized rows into `commodities`, `states`, `markets`, and `market_daily`.

Auto-registers new states/commodities/markets on first sight so ingestion of
a fresh state or commodity doesn't require a manual migration.
"""

from __future__ import annotations

import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

log = structlog.get_logger(__name__)


def _get_or_create(session: Session, table: str, name_col: str, name: str,
                   extra: dict | None = None) -> int:
    row = session.execute(
        text(f"SELECT id FROM {table} WHERE {name_col} = :n"),
        {"n": name},
    ).first()
    if row:
        return int(row[0])
    cols = [name_col] + list((extra or {}).keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    params = {name_col: name, **(extra or {})}
    new_id = session.execute(
        text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"),
        params,
    ).scalar_one()
    return int(new_id)


def _get_or_create_market(session: Session, state_id: int, district: str, name: str) -> int:
    row = session.execute(
        text(
            "SELECT id FROM markets "
            "WHERE state_id = :s AND district = :d AND name = :n"
        ),
        {"s": state_id, "d": district, "n": name},
    ).first()
    if row:
        return int(row[0])
    new_id = session.execute(
        text(
            "INSERT INTO markets (state_id, district, name) "
            "VALUES (:s, :d, :n) RETURNING id"
        ),
        {"s": state_id, "d": district, "n": name},
    ).scalar_one()
    return int(new_id)


_UPSERT_SQL = text(
    """
    INSERT INTO market_daily
        (date, market_id, commodity_id, variety,
         min_price, modal_price, max_price, arrival_tonnes, source)
    VALUES
        (:date, :market_id, :commodity_id, :variety,
         :min_price, :modal_price, :max_price, :arrival_tonnes, :source)
    ON CONFLICT (date, market_id, commodity_id, variety)
    DO UPDATE SET
        min_price      = EXCLUDED.min_price,
        modal_price    = EXCLUDED.modal_price,
        max_price      = EXCLUDED.max_price,
        arrival_tonnes = EXCLUDED.arrival_tonnes,
        source         = EXCLUDED.source,
        ingested_at    = NOW()
    """
)


def upsert_panel(session: Session, df: pd.DataFrame, source: str = "agmarknet") -> int:
    """Upsert a normalized DataFrame. Returns rows written."""
    if df.empty:
        return 0

    # Cache lookups within one batch to avoid re-querying per row.
    state_cache: dict[str, int] = {}
    commodity_cache: dict[str, int] = {}
    market_cache: dict[tuple[int, str, str], int] = {}

    rows_written = 0
    payload: list[dict] = []

    for row in df.itertuples(index=False):
        state = row.state
        commodity = row.commodity
        district = row.district or ""
        market = row.market

        if state not in state_cache:
            state_cache[state] = _get_or_create(session, "states", "name", state)
        state_id = state_cache[state]

        if commodity not in commodity_cache:
            commodity_cache[commodity] = _get_or_create(
                session, "commodities", "name", commodity
            )
        commodity_id = commodity_cache[commodity]

        key = (state_id, district, market)
        if key not in market_cache:
            market_cache[key] = _get_or_create_market(
                session, state_id, district, market
            )
        market_id = market_cache[key]

        payload.append(
            {
                "date": row.date,
                "market_id": market_id,
                "commodity_id": commodity_id,
                "variety": row.variety or "",
                "min_price": row.min_price,
                "modal_price": row.modal_price,
                "max_price": row.max_price,
                "arrival_tonnes": row.arrival_tonnes,
                "source": source,
            }
        )

    if payload:
        session.execute(_UPSERT_SQL, payload)
        rows_written = len(payload)
        log.info("upsert_panel_ok", rows=rows_written)

    return rows_written
