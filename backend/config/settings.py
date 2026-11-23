from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config, loaded from environment (or `.env` file at repo root).

    Fields default to values that match `docker-compose.yml` and `.env.example`,
    so a fresh clone works without a `.env` for local development against the
    default Postgres container.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+psycopg2://freshroute:freshroute@localhost:5433/freshroute"
    )

    # Agmarknet SDK
    agmarknet_request_delay_sec: float = 1.0

    # data.gov.in (Phase 1 live daily feed)
    data_gov_in_api_key: str = ""

    # CEDA Agri-Market Data API (Phase 3 history source; free key, expires)
    ceda_api_key: str = ""
    ceda_base_url: str = "https://api.ceda.ashoka.edu.in/v1"
    # Confirmed by `ceda-probe`: the API uses `Authorization: Bearer <key>`.
    # One of: x-api-key | bearer | authorization | api-key
    ceda_auth_scheme: str = "bearer"
    ceda_request_delay_sec: float = 1.5
    # Last-resort row limit: a response this large is re-requested in pieces. The API
    # was observed returning 1,300-1,500 rows uncut, so this is effectively off; silent
    # caps are instead caught by the round-number checks in CedaClient.fetch_series.
    ceda_max_rows: int = 100_000
    ceda_market_batch: int = 10

    # Open-Meteo (Phase 4)
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"

    # OSRM (Phase 2)
    osrm_base_url: str = "http://localhost:5000"

    # Runtime
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
