"""GET /summary — the four KPI cards on the dashboard home.

Reads the latest snapshot date, counts of states / mandis / commodities,
and the single largest same-day intra-state spread across all commodities.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.api.schemas import SummaryCard, SummaryResponse

router = APIRouter(tags=["summary"])

# Matches markets.PRICE_FLOOR_RS_PER_QUINTAL — kept out of shared constants
# to keep the routers self-contained. If a third router needs it, promote.
_PRICE_FLOOR = 100.0


@router.get("/summary", response_model=SummaryResponse)
def summary(db: Session = Depends(get_db)) -> SummaryResponse:
    latest = db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()

    counts = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM commodities)                        AS commodities,
              (SELECT COUNT(DISTINCT state_id) FROM markets)            AS states,
              (SELECT COUNT(*) FROM markets)                            AS markets,
              (SELECT COUNT(*) FROM market_daily WHERE date = :d)       AS rows_today
            """
        ),
        {"d": latest},
    ).mappings().one()

    top_spread = db.execute(
        text(
            """
            WITH x AS (
              SELECT c.name AS commodity, s.name AS state,
                     MIN(md.modal_price) AS lo,
                     MAX(md.modal_price) AS hi,
                     COUNT(*) AS n
                FROM market_daily md
                JOIN commodities c ON c.id = md.commodity_id
                JOIN markets     m ON m.id = md.market_id
                JOIN states      s ON s.id = m.state_id
               WHERE md.date = :d AND md.modal_price >= :floor
               GROUP BY c.name, s.name
              HAVING COUNT(*) >= 3
            )
            SELECT commodity, state, lo, hi, n,
                   ROUND(((hi - lo) / NULLIF(lo, 0) * 100)::numeric, 1) AS spread_pct
              FROM x
             ORDER BY spread_pct DESC NULLS LAST
             LIMIT 1
            """
        ),
        {"d": latest, "floor": _PRICE_FLOOR},
    ).mappings().first()

    cards = [
        SummaryCard(
            label="Latest",
            value=latest.isoformat() if latest else "—",
            caption="Snapshot date",
        ),
        SummaryCard(
            label="States",
            value=f"{counts['states']}",
            caption=f"{counts['markets']} mandis",
        ),
        SummaryCard(
            label="Prices",
            value=f"{counts['rows_today']:,}",
            caption="Reported today",
        ),
    ]
    if top_spread:
        cards.append(
            SummaryCard(
                label="Widest spread",
                value=f"{top_spread['spread_pct']}%",
                caption=(
                    f"{top_spread['commodity']} · {top_spread['state']}"
                ),
            )
        )
    else:
        cards.append(
            SummaryCard(label="Widest spread", value="—", caption=None)
        )

    return SummaryResponse(snapshot_date=latest, cards=cards)
