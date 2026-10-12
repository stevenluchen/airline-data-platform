DROP TABLE IF EXISTS analytics.dim_aircraft_types;

CREATE TABLE analytics.dim_aircraft_types (
    name TEXT,
    iata TEXT,
    icao TEXT
);