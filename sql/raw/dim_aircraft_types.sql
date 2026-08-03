-- sql/dim_aircraft_types.sql
CREATE TABLE IF NOT EXISTS analytics.dim_aircraft_types (
    name TEXT,
    iata TEXT,
    icao TEXT
);