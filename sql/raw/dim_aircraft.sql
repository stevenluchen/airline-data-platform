-- sql/dim_aircraft.sql
CREATE TABLE IF NOT EXISTS analytics.dim_aircraft (
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
