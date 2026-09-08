"""FreshRoute demo API — read-only surface over `market_daily` + `cost/model`.

Route inventory:
    GET /health                        Liveness ping
    GET /summary                       KPI cards for the dashboard home
    GET /markets/facets                Distinct commodities + states
    GET /markets/arbitrage             Ranked intra-state spreads
    GET /markets/prices                Per-mandi prices for a commodity
    GET /cost/estimate                 Itemized ₹ breakdown for a consignment

Phase 5 will extend this surface with `/recommend` once the forecaster
(Phase 3) and the freshness engine (Phase 4) land.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import costs, markets, summary


def create_app() -> FastAPI:
    app = FastAPI(
        title="FreshRoute API",
        version="0.1.0",
        summary="Read-only demo surface over the Phase 1+2 pipeline.",
    )

    # CORS: local dev only. Tighten before any deployment.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(summary.router)
    app.include_router(markets.router)
    app.include_router(costs.router)
    return app


app = create_app()
