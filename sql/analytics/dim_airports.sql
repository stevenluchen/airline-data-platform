CREATE TABLE IF NOT EXISTS analytics.dim_airports (
    airport_icao VARCHAR(4) PRIMARY KEY,
    airport_iata VARCHAR(3),
    airport_name TEXT,
    city TEXT,
    country TEXT,
    elevation_ft INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    timezone TEXT
);