"""Forecast metadata: is a model loaded, what data it was trained on, how it backtested.

Endpoint:
    GET /forecast/info
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter

from backend.api.schemas import ForecastBacktestRow, ForecastInfoResponse
from backend.forecasting.backtest import RESULTS_PATH, summarize
from backend.forecasting.serve import get_forecaster

router = APIRouter(tags=["forecast"])

# Resolve against the project root so the answer does not depend on the working directory.
_ROOT = Path(__file__).resolve().parents[3]


@router.get("/forecast/info", response_model=ForecastInfoResponse)
def forecast_info() -> ForecastInfoResponse:
    forecaster = get_forecaster()
    if forecaster is None:
        return ForecastInfoResponse(
            available=False,
            note="No trained model found. Run `python -m backend.cli forecast-train`, then restart the API.",
        )

    rows: list[ForecastBacktestRow] = []
    results_file = _ROOT / RESULTS_PATH
    if results_file.exists():
        summary = summarize(pd.read_csv(results_file))
        rows = [
            ForecastBacktestRow(
                horizon_days=int(r.horizon),
                model=str(r.model),
                pinball_loss=float(r.pinball),
                skill_vs_naive=float(r.skill_vs_naive),
                mae_rs_per_quintal=float(r.mae_rs),
                coverage_p10_p90=float(r.coverage),
                band_width_pct=float(r.width) * 100.0,
                test_rows=int(r.n),
            )
            for r in summary.itertuples()
        ]
    return ForecastInfoResponse(
        available=True,
        trained_through=forecaster.trained_through,
        horizons=list(forecaster.model.horizons),
        backtest=rows,
        note=None if rows else "Backtest results not found; run `forecast-backtest`.",
    )
