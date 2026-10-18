"""Market price intelligence — SQL analytics layer.

Provides commodity statistics, state rankings, and per-market price context
enrichment for the recommendation engine and intelligence endpoints.

All queries target the latest available snapshot date.
Every public function gracefully returns None / [] when market_daily is empty.

PERCENTILE_CONT is used as a plain aggregate (not window function) because
PostgreSQL does not support ordered-set aggregates as window functions.
Per-market percentile rank uses PERCENT_RANK(), which IS a valid window function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

PRICE_FLOOR = 100.0  # ₹/quintal — same floor as markets.py and recommender.py


def _latest_date(db: Session) -> date | None:
    return db.execute(text("SELECT MAX(date) FROM market_daily")).scalar()


# ── Dataclasses (internal, consumed by routers + recommender) ──────────────

@dataclass(frozen=True)
class CommodityStats:
    commodity: str
    snapshot_date: date
    national_median: float
    p25: float
    p75: float
    national_max: float
    national_min: float
    mandis_count: int
    states_count: int


@dataclass(frozen=True)
class StateRank:
    state: str
    median_price: float
    max_price: float
    min_price: float
    mandis_reporting: int
    rank: int


@dataclass(frozen=True)
class MarketPriceContext:
    """Price context for a single market; used to enrich recommendations."""
    market_id: int
    price_pct_rank_in_state: float      # 0–100 (100 = highest priced mandi in state)
    vs_state_median_rs_per_qtl: float   # positive = above state median
    vs_national_median_rs_per_qtl: float


@dataclass(frozen=True)
class CommodityOverviewRow:
    commodity: str
    snapshot_date: date
    national_median: float
    national_max: float
    mandis_count: int
    best_state: str
    best_state_median: float


# ── Public analytics functions ─────────────────────────────────────────────

def commodity_stats(db: Session, commodity: str) -> CommodityStats | None:
    """National price statistics for a commodity on the latest snapshot date."""
    d = _latest_date(db)
    if d is None:
        return None

    row = db.execute(
        text("""
            SELECT
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY md.modal_price) AS p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY md.modal_price) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY md.modal_price) AS p75,
                MIN(md.modal_price)            AS min_price,
                MAX(md.modal_price)            AS max_price,
                COUNT(*)                       AS n_mandis,
                COUNT(DISTINCT m.state_id)     AS n_states
            FROM market_daily md
            JOIN commodities c ON c.id = md.commodity_id
            JOIN markets     m ON m.id = md.market_id
            WHERE md.date          = :d
              AND c.name           = :commodity
              AND md.modal_price  >= :floor
        """),
        {"d": d, "commodity": commodity, "floor": PRICE_FLOOR},
    ).mappings().one_or_none()

    if row is None or (row["n_mandis"] or 0) == 0:
        return None

    return CommodityStats(
        commodity=commodity,
        snapshot_date=d,
        national_median=float(row["p50"]),
        p25=float(row["p25"]),
        p75=float(row["p75"]),
        national_max=float(row["max_price"]),
        national_min=float(row["min_price"]),
        mandis_count=int(row["n_mandis"]),
        states_count=int(row["n_states"]),
    )


def state_price_rankings(
    db: Session, commodity: str, min_mandis: int = 2
) -> list[StateRank]:
    """States ranked by median modal price for a commodity today.

    Only includes states with at least `min_mandis` reporting mandis —
    a state with a single mandi is too small to be reliable.
    """
    d = _latest_date(db)
    if d is None:
        return []

    rows = db.execute(
        text("""
            SELECT s.name AS state,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY md.modal_price) AS median_price,
                   MAX(md.modal_price) AS max_price,
                   MIN(md.modal_price) AS min_price,
                   COUNT(*)            AS n
            FROM market_daily md
            JOIN commodities c ON c.id = md.commodity_id
            JOIN markets     m ON m.id = md.market_id
            JOIN states      s ON s.id = m.state_id
            WHERE md.date         = :d
              AND c.name          = :commodity
              AND md.modal_price >= :floor
            GROUP BY s.name
            HAVING COUNT(*) >= :min_n
            ORDER BY median_price DESC
        """),
        {"d": d, "commodity": commodity, "floor": PRICE_FLOOR, "min_n": min_mandis},
    ).mappings().all()

    return [
        StateRank(
            state=r["state"],
            median_price=float(r["median_price"]),
            max_price=float(r["max_price"]),
            min_price=float(r["min_price"]),
            mandis_reporting=int(r["n"]),
            rank=i + 1,
        )
        for i, r in enumerate(rows)
    ]


def build_market_context_map(
    db: Session, commodity: str
) -> dict[int, MarketPriceContext]:
    """For every mandi in the latest snapshot, compute:
      - PERCENT_RANK within state (0–100)
      - premium/discount vs state median (₹/qtl)
      - premium/discount vs national median (₹/qtl)

    Returns a dict keyed on market_id. The recommender calls this once and
    uses it to enrich each ranked result.

    Uses two CTEs — one for state-level medians, one for the national median
    — because PostgreSQL does not support PERCENTILE_CONT as a window function.
    """
    d = _latest_date(db)
    if d is None:
        return {}

    rows = db.execute(
        text("""
            WITH base AS (
                SELECT md.market_id,
                       md.modal_price,
                       m.state_id
                FROM market_daily md
                JOIN commodities c ON c.id = md.commodity_id
                JOIN markets     m ON m.id = md.market_id
                WHERE md.date         = :d
                  AND c.name          = :commodity
                  AND md.modal_price >= :floor
            ),
            state_medians AS (
                SELECT state_id,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY modal_price)
                           AS state_median
                FROM base
                GROUP BY state_id
            ),
            national_median AS (
                SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY modal_price)
                    AS national_median
                FROM base
            ),
            enriched AS (
                SELECT
                    b.market_id,
                    b.modal_price,
                    ROUND(
                        PERCENT_RANK() OVER (
                            PARTITION BY b.state_id ORDER BY b.modal_price
                        )::numeric * 100,
                        0
                    ) AS pct_rank_in_state,
                    sm.state_median,
                    nm.national_median
                FROM base b
                JOIN state_medians sm  ON sm.state_id = b.state_id
                CROSS JOIN national_median nm
            )
            SELECT * FROM enriched
        """),
        {"d": d, "commodity": commodity, "floor": PRICE_FLOOR},
    ).mappings().all()

    return {
        r["market_id"]: MarketPriceContext(
            market_id=r["market_id"],
            price_pct_rank_in_state=float(r["pct_rank_in_state"]),
            vs_state_median_rs_per_qtl=round(
                float(r["modal_price"]) - float(r["state_median"]), 1
            ),
            vs_national_median_rs_per_qtl=round(
                float(r["modal_price"]) - float(r["national_median"]), 1
            ),
        )
        for r in rows
    }


def commodity_overview(db: Session) -> list[CommodityOverviewRow]:
    """One-row summary per commodity: national median, peak price, top state.

    Powers the multi-commodity dashboard widget on the home page.
    Only includes states with >= 2 mandis reporting to avoid single-mandi
    outliers distorting the "best state" label.
    """
    d = _latest_date(db)
    if d is None:
        return []

    rows = db.execute(
        text("""
            WITH base AS (
                SELECT c.name AS commodity,
                       s.name AS state,
                       md.modal_price
                FROM market_daily md
                JOIN commodities c ON c.id = md.commodity_id
                JOIN markets     m ON m.id = md.market_id
                JOIN states      s ON s.id = m.state_id
                WHERE md.date         = :d
                  AND md.modal_price >= :floor
            ),
            national AS (
                SELECT commodity,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY modal_price)
                           AS national_median,
                       MAX(modal_price)  AS national_max,
                       COUNT(*)          AS n_mandis
                FROM base
                GROUP BY commodity
            ),
            state_agg AS (
                SELECT commodity, state,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY modal_price)
                           AS state_median
                FROM base
                GROUP BY commodity, state
                HAVING COUNT(*) >= 2
            ),
            best_state AS (
                SELECT DISTINCT ON (commodity)
                       commodity, state, state_median
                FROM state_agg
                ORDER BY commodity, state_median DESC
            )
            SELECT n.commodity,
                   n.national_median,
                   n.national_max,
                   n.n_mandis,
                   bs.state          AS best_state,
                   bs.state_median   AS best_state_median
            FROM national n
            JOIN best_state bs ON bs.commodity = n.commodity
            ORDER BY n.national_median DESC
        """),
        {"d": d, "floor": PRICE_FLOOR},
    ).mappings().all()

    return [
        CommodityOverviewRow(
            commodity=r["commodity"],
            snapshot_date=d,
            national_median=float(r["national_median"]),
            national_max=float(r["national_max"]),
            mandis_count=int(r["n_mandis"]),
            best_state=r["best_state"],
            best_state_median=float(r["best_state_median"]),
        )
        for r in rows
    ]
