"""FreshRoute API — read-only surface over `market_daily` + decision engine.

Route inventory:
    GET /health                           Liveness ping
    GET /summary                          KPI cards for the dashboard home
    GET /markets/facets                   Distinct commodities + states
    GET /markets/arbitrage                Ranked intra-state spreads
    GET /markets/prices                   Per-mandi prices for a commodity
    GET /cost/estimate                    Itemized ₹ breakdown for a consignment
    GET /recommend/vehicles               Vehicle catalogue
    GET /recommend                        Best mandi ranked by net ₹/tonne
    GET /intel/commodity-summary          National stats + state rankings
    GET /intel/commodity-overview         Multi-commodity dashboard widget
    GET /intel/net-spread                 All reachable mandis, net ₹/quintal
    GET /intel/seasonal                   52-week arrival-index for a commodity+state
    GET /geo/districts                    District centroids for GPS-fallback picker
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import costs, geo, intelligence, markets, recommend, summary


def create_app() -> FastAPI:
    app = FastAPI(
        title="FreshRoute API",
        version="0.2.0",
        summary="Read-only surface: prices, arbitrage, cost model, recommendation, and intelligence.",
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
    app.include_router(recommend.router)
    app.include_router(intelligence.router)
    app.include_router(geo.router)
    return app


app = create_app()
