-- 004_indices.sql — supporting indices for common lookback queries

-- Fast per-commodity time-series scan (used by seasonal index and forecaster feature builds).
CREATE INDEX IF NOT EXISTS market_daily_commodity_date_idx
    ON market_daily (commodity_id, date DESC);

-- Fast per-mandi time-series scan (used by dashboards and quality reports).
CREATE INDEX IF NOT EXISTS market_daily_market_date_idx
    ON market_daily (market_id, date DESC);
