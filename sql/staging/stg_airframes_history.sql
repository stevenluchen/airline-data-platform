DROP TABLE IF EXISTS staging.stg_airframes_history;

CREATE TABLE staging.stg_airframes_history (
    time TEXT,
    icao24 TEXT,
    registration_number TEXT,
    type TEXT,
    "dbFlags" TEXT,
    "ownOp" TEXT,
    year TEXT,
    "desc" TEXT,
    aircraft_category TEXT
);