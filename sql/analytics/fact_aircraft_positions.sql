-- sql/analytics/fact_aircraft_positions.sql
-- DDL for the enriched aircraft positions fact table.
--
-- The per-snapshot INSERT...SELECT that loads this table is the single
-- source of truth in app/transform_state_vectors.py (TRANSFORM_QUERY).
-- Keep the load logic there only; duplicating it here caused the two
-- copies to drift.

CREATE TABLE IF NOT EXISTS analytics.fact_aircraft_positions (
    aircraft_position_id BIGSERIAL PRIMARY KEY,
    snapshot_id UUID NOT NULL,
    api_time BIGINT NOT NULL,
    observed_at TIMESTAMP,
    icao24 VARCHAR(6) NOT NULL,
    callsign TEXT,
    origin_country TEXT,
    airline_icao TEXT,
    airline_iata TEXT,
    airline_name TEXT,
    airline_country TEXT,
    aircraft_registration_number TEXT,
    aircraft_type VARCHAR(4),
    aircraft_type_description TEXT,
    aircraft_category VARCHAR(2),
    aircraft_registered_year VARCHAR(4),
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    baro_altitude DOUBLE PRECISION,
    geo_altitude DOUBLE PRECISION,
    on_ground BOOLEAN,
    velocity DOUBLE PRECISION,
    true_track DOUBLE PRECISION,
    vertical_rate DOUBLE PRECISION,
    squawk VARCHAR(8),
    spi BOOLEAN,
    position_source INTEGER,
    category INTEGER,
    ingested_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_fact_aircraft_positions
ON analytics.fact_aircraft_positions (snapshot_id, icao24, api_time);
