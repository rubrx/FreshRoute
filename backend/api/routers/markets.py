"""Market data endpoints — arbitrage spreads, per-mandi prices, and facet lookups.

Endpoints:
    GET /markets/facets       Distinct commodities and states in the current snapshot.
    GET /markets/arbitrage    Ranked intra-state spreads (high − low mandi within a state).
    GET /markets/prices       Per-mandi modal/min/max for a commodity, sorted by price desc.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.api.schemas import (
    ArbitrageResponse,
    ArbitrageRow,
    Facets,
    MandiPrice,
    MandiPriceList,
)

router = APIRouter(tags=["markets"])

# Anything below ₹100/qtl (₹1/kg) is essentially not a real trade for
# tomato/onion/potato/banana in India — treat as data-entry noise for
# the demo surface. The ingestion pipeline preserves the raw values;
# only the analytical view filters them out. The Phase-3 anomaly detector
# will replace this crude floor with per-commodity statistics.
PRICE_FLOOR_RS_PER_QUINTAL = 100.0


@router.get("/markets/facets", response_model=Facets)
def facets(db: Session = Depends(get_db)) -> Facets:
    """Distinct commodity + state names in `market_daily`. Powers the UI selects."""
    commodities = [
        row[0]
        for row in db.execute(
            text(
                """
                SELECT DISTINCT c.name
                  FROM market_daily md JOIN commodities c ON c.id = md.commodity_id
                 ORDER BY 1
                """
            )
        )
    ]
    states = [
        row[0]
        for row in db.execute(
            text(
                """
                SELECT DISTINCT s.name
                  FROM market_daily md
                  JOIN markets m ON m.id = md.market_id
                  JOIN states  s ON s.id = m.state_id
                 ORDER BY 1
                """
            )
        )
    ]
    return Facets(commodities=commodities, states=states)


@router.get("/markets/arbitrage", response_model=ArbitrageResponse)
def arbitrage(
    commodity: str | None = Query(None, description="Restrict to one commodity"),
    min_reporters: int = Query(3, ge=2, le=200,
                               description="Only include (commodity, state) with at least this many mandis"),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ArbitrageResponse:
    """Same-day intra-state price spreads, ranked."""
    latest = db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()
    if latest is None:
        return ArbitrageResponse(snapshot_date=None, count=0, rows=[])

    sql = text(
        """
        WITH scoped AS (
          SELECT c.name AS commodity, s.name AS state, m.name AS market_name,
                 md.modal_price
            FROM market_daily md
            JOIN commodities c ON c.id = md.commodity_id
            JOIN markets     m ON m.id = md.market_id
            JOIN states      s ON s.id = m.state_id
           WHERE md.date = :d
             AND md.modal_price IS NOT NULL
             AND md.modal_price >= :price_floor
             AND (:commodity IS NULL OR c.name = :commodity)
        ),
        agg AS (
          SELECT commodity, state,
                 COUNT(*) AS n,
                 MIN(modal_price) AS lo,
                 MAX(modal_price) AS hi
            FROM scoped
           GROUP BY commodity, state
          HAVING COUNT(*) >= :min_n
        ),
        with_names AS (
          SELECT a.commodity, a.state, a.n, a.lo, a.hi,
                 (SELECT market_name FROM scoped
                   WHERE commodity=a.commodity AND state=a.state AND modal_price=a.hi
                   LIMIT 1) AS high_market,
                 (SELECT market_name FROM scoped
                   WHERE commodity=a.commodity AND state=a.state AND modal_price=a.lo
                   LIMIT 1) AS low_market
            FROM agg a
        )
        SELECT commodity, state, n, lo, hi, high_market, low_market,
               (hi - lo) AS spread,
               ROUND(((hi - lo) / NULLIF(lo, 0) * 100)::numeric, 1) AS spread_pct
          FROM with_names
         ORDER BY spread_pct DESC NULLS LAST
         LIMIT :limit
        """
    )
    rows = db.execute(
        sql,
        {
            "d": latest,
            "commodity": commodity,
            "min_n": min_reporters,
            "limit": limit,
            "price_floor": PRICE_FLOOR_RS_PER_QUINTAL,
        },
    ).mappings().all()

    return ArbitrageResponse(
        snapshot_date=latest,
        count=len(rows),
        rows=[
            ArbitrageRow(
                commodity=r["commodity"],
                state=r["state"],
                snapshot_date=latest,
                mandis_reporting=r["n"],
                min_price_rs_per_quintal=float(r["lo"]),
                max_price_rs_per_quintal=float(r["hi"]),
                spread_rs_per_quintal=float(r["spread"]),
                spread_pct=float(r["spread_pct"]) if r["spread_pct"] is not None else 0.0,
                high_market=r["high_market"],
                low_market=r["low_market"],
            )
            for r in rows
        ],
    )


@router.get("/markets/prices", response_model=MandiPriceList)
def prices(
    commodity: str = Query(..., description="Exact commodity name (case-sensitive)"),
    state: str | None = Query(None, description="Restrict to one state"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> MandiPriceList:
    """Per-mandi prices for a commodity, ranked highest modal first."""
    latest = db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()
    if latest is None:
        raise HTTPException(status_code=404, detail="market_daily is empty")

    sql = text(
        """
        SELECT md.market_id, s.name AS state, m.district, m.name AS market,
               c.name AS commodity, md.variety,
               md.modal_price, md.min_price, md.max_price, md.date
          FROM market_daily md
          JOIN commodities c ON c.id = md.commodity_id
          JOIN markets     m ON m.id = md.market_id
          JOIN states      s ON s.id = m.state_id
         WHERE md.date = :d
           AND c.name = :commodity
           AND md.modal_price IS NOT NULL
           AND (:state IS NULL OR s.name = :state)
         ORDER BY md.modal_price DESC
         LIMIT :limit
        """
    )
    rows = db.execute(
        sql,
        {"d": latest, "commodity": commodity, "state": state, "limit": limit},
    ).mappings().all()

    return MandiPriceList(
        commodity=commodity,
        state=state,
        snapshot_date=latest,
        count=len(rows),
        rows=[
            MandiPrice(
                market_id=r["market_id"],
                state=r["state"],
                district=r["district"] or "",
                market=r["market"],
                commodity=r["commodity"],
                variety=r["variety"] or None,
                modal_price_rs_per_quintal=float(r["modal_price"]),
                min_price_rs_per_quintal=float(r["min_price"]) if r["min_price"] is not None else None,
                max_price_rs_per_quintal=float(r["max_price"]) if r["max_price"] is not None else None,
                date=r["date"],
            )
            for r in rows
        ],
    )
