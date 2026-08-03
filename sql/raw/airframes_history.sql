-- sql/raw/airframes_history.sql
CREATE TABLE IF NOT EXISTS raw.airframes_history (
    time TEXT,
    icao24 TEXT,
    registration_number TEXT,
    type TEXT,
    dbFlags TEXT,
    ownOp TEXT,
    year TEXT,
    desc TEXT,
    aircraft_category TEXT
);
