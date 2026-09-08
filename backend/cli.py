"""FreshRoute CLI.

Usage:
    python -m backend.cli migrate
    python -m backend.cli backfill --states Maharashtra,Karnataka --commodities Tomato,Onion,Potato,Banana
    python -m backend.cli daily    --states Maharashtra,Karnataka --commodities Tomato,Onion
    python -m backend.cli quality  --min-density 0.6
"""

from __future__ import annotations

import logging
from datetime import date

import structlog
import typer

from backend.config import get_settings

app = typer.Typer(add_completion=False, help="FreshRoute ops CLI")


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.KeyValueRenderer(key_order=["event", "level", "timestamp"]),
        ]
    )


def _split(csv: str) -> list[str]:
    return [item.strip() for item in csv.split(",") if item.strip()]


@app.callback()
def _root() -> None:
    _configure_logging()


@app.command()
def migrate() -> None:
    """Apply any pending SQL migrations."""
    from backend.db.migrate import apply_pending

    applied = apply_pending()
    typer.echo(f"Applied {len(applied)} migration(s): {applied or '—'}")


@app.command()
def backfill(
    states: str = typer.Option(..., help="Comma-separated state names"),
    commodities: str = typer.Option(..., help="Comma-separated commodity names"),
    start: str = typer.Option("2007-01-01", help="ISO start date"),
    end: str | None = typer.Option(None, help="ISO end date (default: today)"),
) -> None:
    """Backfill historical Agmarknet data for the state × commodity matrix."""
    from backend.ingestion.backfill import backfill_matrix

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end) if end else None
    results = backfill_matrix(_split(states), _split(commodities), start=start_d, end=end_d)
    for k, v in results.items():
        typer.echo(f"{k}: {v} rows")


@app.command()
def daily(
    states: str = typer.Option(..., help="Comma-separated state names"),
    commodities: str = typer.Option(..., help="Comma-separated commodity names"),
    lookback_days: int = typer.Option(7, help="How many days back to sweep"),
) -> None:
    """Incremental pull for the last N days."""
    from backend.ingestion.daily import daily_pull

    results = daily_pull(_split(states), _split(commodities), lookback_days=lookback_days)
    for k, v in results.items():
        typer.echo(f"{k}: {v} rows")


@app.command("pull-datagovin")
def pull_datagovin(
    states: str | None = typer.Option(
        None, help="Comma-separated state names to keep; blank = all states"
    ),
    commodities: str | None = typer.Option(
        None, help="Comma-separated commodity names to keep; blank = all"
    ),
    no_save_raw: bool = typer.Option(
        False, help="Skip writing the raw snapshot parquet to data/raw/datagovin/"
    ),
) -> None:
    """Pull today's data.gov.in AGMARKNET snapshot into `market_daily`.

    Prices only (no arrivals). Snapshot-only source — history accumulates
    across daily runs. See `docs/phase1-data-source-note.md`.
    """
    from backend.ingestion.pull_datagovin import pull_snapshot

    result = pull_snapshot(
        states=_split(states) if states else None,
        commodities=_split(commodities) if commodities else None,
        save_raw=not no_save_raw,
    )
    for k, v in result.items():
        typer.echo(f"{k}: {v}")


@app.command()
def quality(
    min_density: float = typer.Option(0.60, help="Minimum reporting density to keep a mandi"),
    window_start: str | None = typer.Option(None, help="ISO date; default = 3 years ago"),
    window_end: str | None = typer.Option(None, help="ISO date; default = today"),
) -> None:
    """Emit `docs/data-quality-report.md`."""
    from backend.ingestion.quality import write_report

    ws = date.fromisoformat(window_start) if window_start else None
    we = date.fromisoformat(window_end) if window_end else None
    path = write_report(min_density=min_density, window_start=ws, window_end=we)
    typer.echo(f"Wrote {path}")


@app.command()
def seasonal(
    min_years: int = typer.Option(3, help="Drop (commodity, state) with fewer distinct years"),
    only_active: bool = typer.Option(True, help="Use only mandis marked is_active in `markets`"),
    write_docs: bool = typer.Option(True, help="Also emit docs/seasonal-calendar.md"),
) -> None:
    """Compute the empirical seasonal arrival index and write it to
    `data/processed/seasonal_index.parquet`."""
    from backend.forecasting.seasonal import write_markdown, write_parquet

    parquet = write_parquet(only_active=only_active)
    typer.echo(f"Wrote {parquet}")
    if write_docs:
        md = write_markdown(only_active=only_active)
        typer.echo(f"Wrote {md}")


@app.command()
def geocode(
    force: bool = typer.Option(False, help="Re-geocode mandis that already have coords"),
) -> None:
    """Geocode active mandis via Nominatim (polite, 1 request/second)."""
    from backend.ingestion.geocode import geocode_all

    stats = geocode_all(force=force)
    for k, v in stats.items():
        typer.echo(f"{k}: {v}")


@app.command()
def distances(
    origins: str | None = typer.Option(None, help="Comma-separated origin market_ids; blank = all"),
    dests: str | None = typer.Option(None, help="Comma-separated dest market_ids; blank = all"),
    no_polyline: bool = typer.Option(False, help="Skip polyline storage (smaller cache)"),
    force: bool = typer.Option(False, help="Recompute even if pair is cached"),
) -> None:
    """Compute + cache OSRM routes for mandi pairs into
    `data/processed/distance_matrix.parquet`."""
    from backend.freshness.distance_matrix import compute_matrix

    def _ids(csv: str | None) -> list[int] | None:
        if not csv:
            return None
        return [int(x.strip()) for x in csv.split(",") if x.strip()]

    df = compute_matrix(
        origin_ids=_ids(origins),
        dest_ids=_ids(dests),
        include_polyline=not no_polyline,
        force=force,
    )
    typer.echo(f"Matrix has {len(df)} pairs cached")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="uvicorn --reload for local dev"),
) -> None:
    """Run the FastAPI demo API (powers the dashboard)."""
    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    app()
