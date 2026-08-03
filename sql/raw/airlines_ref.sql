-- sql/dim_airlines.sql
CREATE TABLE IF NOT EXISTS raw.airlines_ref (
    icao TEXT,
    iata TEXT,
    name TEXT,
    icao_callsign TEXT
);