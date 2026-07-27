-- sql/create_tables.sql
-- raw OpenSky state vectors
CREATE TABLE IF NOT EXISTS raw.state_vectors (

    id BIGSERIAL PRIMARY KEY,
    api_time BIGINT,
    icao24 VARCHAR(6),
    callsign TEXT,
    origin_country TEXT,
    time_position BIGINT,
    last_contact BIGINT,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    baro_altitude DOUBLE PRECISION,
    on_ground BOOLEAN,
    velocity DOUBLE PRECISION,
    true_track DOUBLE PRECISION,
    vertical_rate DOUBLE PRECISION,
    sensors JSONB,
    geo_altitude DOUBLE PRECISION,
    squawk VARCHAR(8),
    spi BOOLEAN,
    position_source INTEGER,
    category INTEGER,
    ingested_at TIMESTAMP DEFAULT NOW(),
    snapshot_id UUID
);

-- deduped aircraft dimension table
CREATE OR REPLACE TABLE analytics.dim_aircraft (
    icao24 VARCHAR(6) PRIMARY KEY,
    registration_number VARCHAR(20),
    "type" VARCHAR(4),
    "desc" VARCHAR(150),

    operator VARCHAR(150),
    year VARCHAR(4),
    aircraft_category VARCHAR(2),

    last_updated TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- populate aircraft dimension table
INSERT INTO analytics.dim_aircraft
SELECT
    icao24,
    registration_number,
    "type",
    "desc",
    "ownOp" as operator,
    "year",
    aircraft_category,
    time::TIMESTAMP AS last_updated
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY icao24
            ORDER BY time DESC
        ) as rn
    FROM raw.airframes_history
    WHERE length(icao24) = 6
) t
WHERE rn = 1;
