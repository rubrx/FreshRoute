"""Seasonal arrival index — the empirical crop calendar.

For each (commodity, state, ISO week), compute:

    AI(commodity, state, w) = median arrivals in week w  /  annual median arrivals

Interpretation:
    AI > 1.5  → glut window   (arrivals well above average; prices tend to crash)
    AI ≈ 1.0  → normal
    AI < 0.6  → lean window   (arrivals well below average; prices tend to spike)

This is the empirical calendar per `buildplan.md §4.2` — derived from ~10+ years
of Agmarknet arrivals, not hard-coded. Feeds:
- the dashboard heatmap (Phase 5)
- glut early-warning tuning (Phase 3, arrival forecaster)
- LightGBM features (Phase 3, price + arrival models)

Panel-completeness caveat: markets vary in reporting density. We aggregate to
(commodity × state × week) so a single sparse mandi doesn't distort the index.
Mandis below the density threshold (see `ingestion/quality.py`) should be
filtered before running this — see `_active_market_filter`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import text

from backend.db.connection import get_engine

log = structlog.get_logger(__name__)

OUTPUT_PATH = Path("data/processed/seasonal_index.parquet")

_ARRIVALS_SQL = text(
    """
    SELECT
        c.name        AS commodity,
        s.name        AS state,
        md.date       AS date,
        md.arrival_tonnes
    FROM market_daily md
    JOIN markets     m ON m.id = md.market_id
    JOIN states      s ON s.id = m.state_id
    JOIN commodities c ON c.id = md.commodity_id
    WHERE md.arrival_tonnes IS NOT NULL
      AND md.arrival_tonnes > 0
      AND (:only_active IS FALSE OR m.is_active = TRUE)
    """
)


def _load_arrivals(only_active: bool = True) -> pd.DataFrame:
    """Pull the full arrivals panel. Small enough (~millions of rows) to hold
    in memory for this analysis. If it grows past that, aggregate in SQL."""
    df = pd.read_sql(_ARRIVALS_SQL, get_engine(), params={"only_active": only_active})
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["iso_week"] = df["date"].dt.isocalendar().week.astype(int)
    df["iso_year"] = df["date"].dt.isocalendar().year.astype(int)
    return df


def compute(only_active: bool = True, min_years: int = 3) -> pd.DataFrame:
    """Return a DataFrame with columns:

        commodity, state, iso_week, median_arrivals_week,
        weekly_baseline, arrival_index, years_covered

    `weekly_baseline` is the annual median divided by 52 — a per-week
    baseline that `median_arrivals_week` is compared against.

    `min_years` — drop (commodity, state) combinations that don't have arrivals
    reported in at least this many distinct ISO years. Under 3 years is too
    little to trust the median-of-medians logic.
    """
    raw = _load_arrivals(only_active=only_active)
    if raw.empty:
        log.warning("seasonal_no_data")
        return pd.DataFrame(
            columns=[
                "commodity", "state", "iso_week", "median_arrivals_week",
                "weekly_baseline", "arrival_index", "years_covered",
            ]
        )

    # Weekly totals per (commodity, state, iso_year, iso_week).
    # A "week's arrival" is the sum across all mandis that reported that week.
    weekly = (
        raw.groupby(["commodity", "state", "iso_year", "iso_week"], as_index=False)
        ["arrival_tonnes"].sum()
        .rename(columns={"arrival_tonnes": "weekly_arrivals"})
    )

    # Filter (commodity, state) by minimum years covered.
    year_counts = weekly.groupby(["commodity", "state"])["iso_year"].nunique()
    kept = year_counts[year_counts >= min_years].reset_index()[["commodity", "state"]]
    weekly = weekly.merge(kept, on=["commodity", "state"], how="inner")
    if weekly.empty:
        log.warning("seasonal_all_filtered", min_years=min_years)
        return pd.DataFrame()

    # Median across years for each (commodity, state, iso_week).
    median_week = (
        weekly.groupby(["commodity", "state", "iso_week"], as_index=False)
        ["weekly_arrivals"].median()
        .rename(columns={"weekly_arrivals": "median_arrivals_week"})
    )

    # Annual median: median across years of the *annual total* for that
    # (commodity, state), then divide by 52 to get a comparable weekly baseline.
    annual = (
        weekly.groupby(["commodity", "state", "iso_year"], as_index=False)
        ["weekly_arrivals"].sum()
        .rename(columns={"weekly_arrivals": "annual_arrivals"})
    )
    median_annual = (
        annual.groupby(["commodity", "state"], as_index=False)
        ["annual_arrivals"].median()
        .rename(columns={"annual_arrivals": "weekly_baseline"})
    )
    median_annual["weekly_baseline"] = median_annual["weekly_baseline"] / 52.0

    years_covered = (
        year_counts.reset_index().rename(columns={"iso_year": "years_covered"})
    )

    out = (
        median_week.merge(median_annual, on=["commodity", "state"], how="left")
                   .merge(years_covered, on=["commodity", "state"], how="left")
    )
    out["arrival_index"] = out["median_arrivals_week"] / out["weekly_baseline"]
    out = out.sort_values(["commodity", "state", "iso_week"]).reset_index(drop=True)

    log.info(
        "seasonal_compute_ok",
        rows=len(out),
        commodities=out["commodity"].nunique(),
        states=out["state"].nunique(),
    )
    return out


def _label(index: float) -> str:
    if index >= 1.5:
        return "glut"
    if index <= 0.6:
        return "lean"
    return "normal"


def write_parquet(path: Path = OUTPUT_PATH, only_active: bool = True) -> Path:
    df = compute(only_active=only_active)
    if df.empty:
        log.warning("seasonal_nothing_to_write")
        return path
    df["window"] = df["arrival_index"].map(_label)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("seasonal_parquet_written", path=str(path), rows=len(df))
    return path


def render_markdown_heatmap(df: pd.DataFrame) -> str:
    """Text-only heatmap per commodity × state, useful in the docs writeup.
    Rows = state, columns = ISO week 1..52, cells = glut/lean/normal symbol."""
    lines: list[str] = []
    lines.append("# Seasonal calendar (empirical)")
    lines.append("")
    lines.append("Legend: `▲` = glut (AI ≥ 1.5), `▼` = lean (AI ≤ 0.6), `·` = normal.")
    lines.append("")

    if df.empty:
        lines.append("_No data — run backfill first, then re-run `freshroute seasonal`._")
        return "\n".join(lines)

    for commodity, cdf in df.groupby("commodity"):
        lines.append(f"## {commodity}")
        lines.append("")
        header = "| state | " + " | ".join(str(w) for w in range(1, 53)) + " |"
        sep = "|---|" + "|".join("---" for _ in range(52)) + "|"
        lines.append(header)
        lines.append(sep)
        for state, sdf in cdf.groupby("state"):
            by_week = {int(r.iso_week): float(r.arrival_index) for r in sdf.itertuples(index=False)}
            cells = []
            for w in range(1, 53):
                ai = by_week.get(w)
                if ai is None:
                    cells.append(" ")
                elif ai >= 1.5:
                    cells.append("▲")
                elif ai <= 0.6:
                    cells.append("▼")
                else:
                    cells.append("·")
            lines.append(f"| {state} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def write_markdown(path: Path = Path("docs/seasonal-calendar.md"),
                   only_active: bool = True) -> Path:
    df = compute(only_active=only_active)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_heatmap(df))
    log.info("seasonal_markdown_written", path=str(path))
    return path
