-- sql/staging/fact_aircraft_positions.sql
-- Create the enriched aircraft positions fact table and populate it
-- from the raw OpenSky state vectors joined to airline and aircraft dims.

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

INSERT INTO analytics.fact_aircraft_positions (
    snapshot_id,
    api_time,
    observed_at,
    icao24,
    callsign,
    origin_country,
    airline_icao,
    airline_iata,
    airline_name,
    airline_country,
    aircraft_registration_number,
    aircraft_type,
    aircraft_type_description,
    aircraft_category,
    aircraft_registered_year,
    longitude,
    latitude,
    baro_altitude,
    geo_altitude,
    on_ground,
    velocity,
    true_track,
    vertical_rate,
    squawk,
    spi,
    position_source,
    category,
    ingested_at
)
SELECT
    sv.snapshot_id,
    sv.api_time,
    TO_TIMESTAMP(sv.api_time) AS observed_at,
    sv.icao24,
    sv.callsign,
    sv.origin_country,
    al.icao AS airline_icao,
    al.iata AS airline_iata,
    al.airline_name,
    al.airline_country,
    ac.registration_number AS aircraft_registration_number,
    ac."type" AS aircraft_type,
    ac."desc" AS aircraft_type_description,
    ac.aircraft_category,
    ac.year AS aircraft_registered_year,
    sv.longitude,
    sv.latitude,
    sv.baro_altitude,
    sv.geo_altitude,
    sv.on_ground,
    sv.velocity,
    sv.true_track,
    sv.vertical_rate,
    sv.squawk,
    sv.spi,
    sv.position_source,
    sv.category,
    sv.ingested_at
FROM raw.state_vectors sv
LEFT JOIN analytics.dim_airlines al
    ON UPPER(LEFT(sv.callsign, 3)) = UPPER(al.icao)
LEFT JOIN analytics.dim_aircraft ac
    ON sv.icao24 = ac.icao24
WHERE sv.snapshot_id = :snapshot_id
ON CONFLICT (snapshot_id, icao24, api_time) DO NOTHING;
