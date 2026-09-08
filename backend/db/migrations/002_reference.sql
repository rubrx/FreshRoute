-- 002_reference.sql — reference tables for commodities, states, markets (mandis)

CREATE TABLE IF NOT EXISTS commodities (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,     -- e.g. 'Tomato', 'Onion'
    category     TEXT,                     -- 'vegetable' | 'fruit' | 'pulse' | ...
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS states (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,     -- e.g. 'Maharashtra'
    code         TEXT UNIQUE,              -- e.g. 'MH'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS markets (
    id           SERIAL PRIMARY KEY,
    state_id     INTEGER NOT NULL REFERENCES states(id) ON DELETE RESTRICT,
    district     TEXT,
    name         TEXT NOT NULL,            -- Agmarknet market name

    -- Geocoding — populated in Phase 2 via Nominatim.
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    geocode_source TEXT,                   -- 'nominatim' | 'manual' | NULL

    -- Reporting-density decision from Phase 1 quality gate.
    reporting_density  DOUBLE PRECISION,   -- 0..1, share of expected days present
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (state_id, district, name)
);

CREATE INDEX IF NOT EXISTS markets_state_idx    ON markets(state_id);
CREATE INDEX IF NOT EXISTS markets_active_idx   ON markets(is_active) WHERE is_active;

-- Seed the four Phase 1 commodities. Add more later without a migration
-- by inserting rows directly, or via ingestion auto-registration.
INSERT INTO commodities (name, category) VALUES
    ('Tomato',  'vegetable'),
    ('Onion',   'vegetable'),
    ('Potato',  'vegetable'),
    ('Banana',  'fruit')
ON CONFLICT (name) DO NOTHING;
