"""FreshRoute CLI.

Usage:
    python -m backend.cli migrate
    python -m backend.cli backfill --states Maharashtra,Karnataka --commodities Tomato,Onion,Potato,Banana
    python -m backend.cli daily    --states Maharashtra,Karnataka --commodities Tomato,Onion
    python -m backend.cli quality  --min-density 0.6
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

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
    """Backfill historical Agmarknet data for the state × commodity matrix.

    NOTE: currently broken — the Agmarknet API now requires a CAPTCHA on every
    request. Use `ceda-fetch` + `ceda-load` for history instead.
    """
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


@app.command("load-snapshots")
def load_snapshots() -> None:
    """Replay every saved data.gov.in snapshot in data/raw/datagovin/ into `market_daily`."""
    from backend.ingestion.pull_datagovin import load_saved_snapshots

    for k, v in load_saved_snapshots().items():
        typer.echo(f"{k}: {v}")


@app.command("ceda-probe")
def ceda_probe(
    cap_test: bool = typer.Option(False, "--cap-test", help="Also run the row-cap test (~30 extra API calls)"),
) -> None:
    """Find the working CEDA base URL + auth scheme and show a sample response.

    Needs CEDA_API_KEY in .env. Prints no secrets. Every run spends part of your
    rate-limited quota, so don't loop it.
    """
    from backend.ingestion.ceda_fetch import probe

    for line in probe(cap_test=cap_test):
        typer.echo(line)


@app.command("export-panel")
def export_panel_cmd() -> None:
    """Dump every price in the database to data/processed/panel.parquet (input to forecasting)."""
    from backend.forecasting.panel import PANEL_PATH, export_panel

    df = export_panel()
    typer.echo(f"{len(df):,} rows, {df['market_id'].nunique()} markets -> {PANEL_PATH}")
    typer.echo(df.groupby(["state", "commodity"]).size().to_string())


@app.command("forecast-backtest")
def forecast_backtest(
    years: str = typer.Option("2022,2023,2024,2025", help="Test years (expanding-window folds)"),
    horizons: str = typer.Option("1,2,3", help="Forecast horizons in days"),
    rounds: int = typer.Option(300, help="Boosting rounds per LightGBM model"),
) -> None:
    """Backtest the P10/P50/P90 forecaster against naive baselines; writes docs/forecast-backtest.md."""
    from backend.forecasting.backtest import (
        PREDICTIONS_PATH, REPORT_PATH, RESULTS_PATH, run_backtest, summarize, write_report,
    )
    from backend.forecasting.features import make_dataset
    from backend.forecasting.panel import load_series

    series = load_series()
    ds, enc = make_dataset(series)
    info = {
        "price observations used": f"{len(series):,}",
        "mandi-commodity series": f"{series.groupby(['market_id', 'commodity']).ngroups:,}",
        "mandis": f"{series['market_id'].nunique():,}",
        "states": ", ".join(sorted(series["state"].unique())),
        "commodities": ", ".join(sorted(series["commodity"].unique())),
        "dates": f"{series['date'].min().date()} to {series['date'].max().date()}",
    }
    results, preds = run_backtest(
        ds, enc, test_years=[int(y) for y in _split(years)],
        horizons=[int(h) for h in _split(horizons)], rounds=rounds,
    )
    if results.empty:
        typer.echo("No fold had enough data; nothing to report.")
        raise typer.Exit(1)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_PATH, index=False)
    preds.to_parquet(PREDICTIONS_PATH, index=False)
    write_report(results, REPORT_PATH, info=info)
    typer.echo(summarize(results).round(4).to_string(index=False))
    typer.echo(f"\nReport: {REPORT_PATH}\nPredictions: {PREDICTIONS_PATH}")


@app.command("forecast-train")
def forecast_train(
    horizons: str = typer.Option("1,2,3"),
    rounds: int = typer.Option(300),
) -> None:
    """Train the final forecaster on all data and save it to data/models/forecaster.pkl."""
    from backend.forecasting.features import make_dataset
    from backend.forecasting.model import MODEL_PATH, Forecaster
    from backend.forecasting.panel import load_series

    ds, enc = make_dataset(load_series())
    model = Forecaster.fit(ds, enc, horizons=[int(h) for h in _split(horizons)], rounds=rounds)
    model.save()
    typer.echo(f"Saved {MODEL_PATH} (trained on data through {model.trained_through})")


@app.command("ceda-scope")
def ceda_scope() -> None:
    """Write data/reference/ceda_scope.csv: the mandis in our live data (limits what `ceda-fetch` downloads).

    Run after `pull-datagovin` / `load-snapshots`. The CSV is small and can be sent to
    anyone running a slice of the download; they need no database.
    """
    from backend.ingestion.ceda_loader import write_scope

    df = write_scope()
    typer.echo(f"{len(df)} rows, {df[['state', 'district', 'market']].drop_duplicates().shape[0]} mandis")
    typer.echo(df.groupby(["state", "commodity"])["market"].nunique().to_string())


@app.command("ceda-explore")
def ceda_explore(
    commodity_id: int = typer.Option(78, help="CEDA commodity id (78 = Tomato)"),
    state_id: int = typer.Option(29, help="CEDA state id (29 = Karnataka)"),
    year: int = typer.Option(2022),
) -> None:
    """Spend 3 API calls to learn whether one request can return a whole state.

    CEDA allows only 40 calls per hour per key, so this decides how the download is done.
    """
    from backend.ingestion.ceda_fetch import explore

    for line in explore(commodity_id, state_id, year):
        typer.echo(line)


def _limit_stop_message(exc: Exception) -> str:
    """Tell the user when to re-run after the hourly CEDA limit stopped the download."""
    secs = getattr(exc, "retry_after", None)
    if secs:
        back = datetime.now() + timedelta(seconds=secs + 10)
        when = f"in about {round(secs / 60)} minutes (around {back:%H:%M})"
    else:
        when = "in about an hour"
    return (
        "Hourly CEDA request limit reached, stopping. Everything downloaded so far is saved.\n"
        f"Run the same command again {when}; it continues where it left off."
    )


@app.command("ceda-fetch")
def ceda_fetch(
    states: str = typer.Option(..., help="Comma-separated state names, e.g. Karnataka,Maharashtra,Tamil Nadu"),
    commodities: str = typer.Option(..., help="Comma-separated commodity names, e.g. Tomato,Onion,Potato,Banana"),
    start: str = typer.Option("2018-01-01", help="ISO start date"),
    end: str = typer.Option("2025-12-31", help="ISO end date (CEDA data currently stops around Oct 2025)"),
    kinds: str = typer.Option("price,quantity", help="price, quantity or both"),
    window_days: int = typer.Option(365, help="Days per request window (budget is only 40 calls/hour; the client splits any response that looks truncated)"),
    batch_size: int = typer.Option(0, help="Markets per request (0 = use CEDA_MARKET_BATCH, default 10)"),
    scope_file: str = typer.Option("", help="Limit the download to the mandis listed in this CSV (from `ceda-scope`), e.g. data/reference/ceda_scope.csv"),
    wait: bool = typer.Option(False, "--wait", help="Sleep through the hourly limit and keep going, instead of stopping"),
) -> None:
    """Download CEDA history into data/raw/ceda/ (resumable; newest years first).

    Run `ceda-probe` first and put the base URL / auth scheme it reports in .env.
    Re-running skips chunks that are already on disk.

    When CEDA's hourly request limit (40 calls) is used up, this STOPS and tells you
    when to run it again; progress is saved. Add --wait to sleep through the limit instead.
    """
    from backend.ingestion.ceda_client import CedaAuthError, CedaClient, CedaError, CedaRateLimited
    from backend.ingestion.ceda_fetch import fetch_state_commodity, load_scope, with_backoff

    client = CedaClient(wait_on_limit=wait)
    try:
        commodities_df = with_backoff(client.commodities)
        geographies_df = with_backoff(client.geographies)
    except CedaRateLimited as exc:
        typer.echo(_limit_stop_message(exc))
        raise typer.Exit(2)
    start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
    scope_df = load_scope(Path(scope_file)) if scope_file else None

    for st in _split(states):
        for cm in _split(commodities):
            typer.echo(f"== {cm} / {st}")
            try:
                res = fetch_state_commodity(
                    client, cm, st, start_d, end_d,
                    kinds=tuple(_split(kinds)),
                    batch_size=batch_size or None,
                    window_days=window_days,
                    scope=scope_df,
                    commodities=commodities_df, geographies=geographies_df,
                )
            except CedaAuthError as exc:
                typer.echo(f"Auth failed (key expired or wrong scheme?): {exc}")
                raise typer.Exit(1)
            except CedaRateLimited as exc:
                typer.echo(_limit_stop_message(exc))
                raise typer.Exit(2)
            except CedaError as exc:
                typer.echo(f"Skipping {cm}/{st}: {exc}")
                continue
            typer.echo(f"   {res}")


@app.command("ceda-map")
def ceda_map(
    states: str = typer.Option(...),
    commodities: str = typer.Option(...),
) -> None:
    """Match cached CEDA markets to OUR markets; writes data/processed/ceda_market_crosswalk.csv.

    Our market names are never changed. Fix unmatched ones by adding rows to
    data/reference/market_aliases.csv, then re-run.
    """
    from backend.ingestion.ceda_loader import CROSSWALK_PATH, run_map

    cw = run_map(_split(states), _split(commodities))
    typer.echo(cw["method"].value_counts().to_string())
    typer.echo(f"Review file: {CROSSWALK_PATH}")


@app.command("ceda-load")
def ceda_load(
    states: str = typer.Option(...),
    commodities: str = typer.Option(...),
    dry_run: bool = typer.Option(False, help="Map and count rows but write nothing"),
) -> None:
    """Load cached CEDA data into `market_daily` under our market names."""
    from backend.ingestion.ceda_loader import run_load

    for k, v in run_load(_split(states), _split(commodities), dry_run=dry_run).items():
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
