"""Data quality checks.

Computes per-market reporting density, panel gaps, duplicate collisions, and
flags unit anomalies (10× price typos are common in Agmarknet).

Emits both a summary dict for programmatic use and, when requested, a
Markdown report to `docs/data-quality-report.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import text

from backend.db.connection import get_engine

log = structlog.get_logger(__name__)

# Prices are ₹/quintal in Agmarknet. Anything an order of magnitude above the
# median for that commodity+market is almost certainly a typo (₹10000 vs ₹1000).
PRICE_TYPO_MULTIPLIER = 8.0
DEFAULT_MIN_DENSITY = 0.60


@dataclass
class MarketQuality:
    market_id: int
    market_name: str
    state_name: str
    commodity_name: str
    first_seen: date
    last_seen: date
    total_days_in_window: int
    days_reported: int
    density: float
    duplicate_count: int
    price_typo_count: int


@dataclass
class QualityReport:
    window_start: date
    window_end: date
    per_market: list[MarketQuality] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([m.__dict__ for m in self.per_market])


def _query_panel(window_start: date, window_end: date) -> pd.DataFrame:
    sql = text(
        """
        SELECT
            md.date,
            md.market_id,
            m.name       AS market_name,
            s.name       AS state_name,
            c.name       AS commodity_name,
            md.variety,
            md.modal_price
        FROM market_daily md
        JOIN markets     m ON m.id = md.market_id
        JOIN states      s ON s.id = m.state_id
        JOIN commodities c ON c.id = md.commodity_id
        WHERE md.date BETWEEN :start AND :end
        """
    )
    return pd.read_sql(sql, get_engine(), params={"start": window_start, "end": window_end})


def compute(window_start: date | None = None, window_end: date | None = None) -> QualityReport:
    window_end = window_end or date.today()
    window_start = window_start or (window_end - timedelta(days=365 * 3))
    total_days = (window_end - window_start).days + 1

    df = _query_panel(window_start, window_end)
    if df.empty:
        log.warning("quality_no_data")
        return QualityReport(window_start=window_start, window_end=window_end)

    report = QualityReport(window_start=window_start, window_end=window_end)

    grouped = df.groupby(["market_id", "market_name", "state_name", "commodity_name"])
    for (mid, mname, sname, cname), sub in grouped:
        days_reported = sub["date"].nunique()
        density = days_reported / total_days

        # A duplicate here is (date, variety) collisions — the natural key
        # allows multiple varieties per day, so a real collision means the
        # SDK returned near-duplicate rows.
        duplicate_count = int(sub.duplicated(subset=["date", "variety"]).sum())

        median_modal = sub["modal_price"].median()
        if pd.notna(median_modal) and median_modal > 0:
            typo_mask = sub["modal_price"] > (median_modal * PRICE_TYPO_MULTIPLIER)
            price_typo_count = int(typo_mask.sum())
        else:
            price_typo_count = 0

        report.per_market.append(
            MarketQuality(
                market_id=int(mid),
                market_name=str(mname),
                state_name=str(sname),
                commodity_name=str(cname),
                first_seen=sub["date"].min(),
                last_seen=sub["date"].max(),
                total_days_in_window=total_days,
                days_reported=int(days_reported),
                density=float(density),
                duplicate_count=duplicate_count,
                price_typo_count=price_typo_count,
            )
        )

    return report


def render_markdown(report: QualityReport, min_density: float = DEFAULT_MIN_DENSITY) -> str:
    df = report.to_dataframe()
    if df.empty:
        return "# Data Quality Report\n\n_No data in the requested window._\n"

    kept = df[df["density"] >= min_density]
    dropped = df[df["density"] < min_density]

    lines: list[str] = []
    lines.append("# Data Quality Report")
    lines.append("")
    lines.append(f"- Window: **{report.window_start.isoformat()} → {report.window_end.isoformat()}**")
    lines.append(f"- Density threshold: **{min_density:.0%}**")
    lines.append(f"- Markets above threshold: **{len(kept)}**")
    lines.append(f"- Markets below threshold: **{len(dropped)}**")
    lines.append("")

    lines.append("## Markets kept (≥ threshold)")
    lines.append("")
    lines.append("| state | market | commodity | density | days | typos | dupes |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in kept.sort_values(["state_name", "market_name", "commodity_name"]).itertuples(index=False):
        lines.append(
            f"| {r.state_name} | {r.market_name} | {r.commodity_name} "
            f"| {r.density:.2%} | {r.days_reported} | {r.price_typo_count} | {r.duplicate_count} |"
        )

    if not dropped.empty:
        lines.append("")
        lines.append("## Markets dropped (< threshold)")
        lines.append("")
        lines.append("| state | market | commodity | density |")
        lines.append("|---|---|---|---:|")
        for r in dropped.sort_values("density").itertuples(index=False):
            lines.append(
                f"| {r.state_name} | {r.market_name} | {r.commodity_name} | {r.density:.2%} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_report(
    path: Path = Path("docs/data-quality-report.md"),
    min_density: float = DEFAULT_MIN_DENSITY,
    window_start: date | None = None,
    window_end: date | None = None,
) -> Path:
    report = compute(window_start=window_start, window_end=window_end)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report, min_density=min_density))
    log.info("quality_report_written", path=str(path))
    return path
