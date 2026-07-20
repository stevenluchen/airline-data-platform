-- sql/create_tables.sql

CREATE TABLE IF NOT EXISTS raw_opensky_states (

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