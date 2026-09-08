-- 003_panel.sql — market_daily hypertable (the price/arrival panel)

CREATE TABLE IF NOT EXISTS market_daily (
    date            DATE          NOT NULL,
    market_id       INTEGER       NOT NULL REFERENCES markets(id)     ON DELETE CASCADE,
    commodity_id    INTEGER       NOT NULL REFERENCES commodities(id) ON DELETE CASCADE,

    -- Variety can vary within (date, market, commodity) — kept in the natural key.
    -- Empty string when Agmarknet reports no variety, so the unique constraint stays honest.
    variety         TEXT          NOT NULL DEFAULT '',

    min_price       NUMERIC(12,2),        -- ₹/quintal
    modal_price     NUMERIC(12,2),
    max_price       NUMERIC(12,2),
    arrival_tonnes  NUMERIC(12,3),        -- tonnes/day

    source          TEXT          NOT NULL DEFAULT 'agmarknet',
    ingested_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- Idempotent upsert key. TimescaleDB requires the partitioning column (date)
    -- to be part of any unique constraint on a hypertable.
    CONSTRAINT market_daily_natural_key UNIQUE (date, market_id, commodity_id, variety)
);

-- Convert to hypertable partitioned on date, 1-month chunks.
SELECT create_hypertable(
    'market_daily',
    'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists       => TRUE
);
