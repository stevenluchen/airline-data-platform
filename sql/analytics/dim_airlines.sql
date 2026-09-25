-- sql/analytics/dim_airlines.sql
-- Rerunnable: drops and rebuilds from staging each run.
DROP TABLE IF EXISTS analytics.dim_airlines;

CREATE TABLE analytics.dim_airlines AS
SELECT
    icao,
    iata,
    airline_name,
    airline_country,
    icao_callsign as callsign
FROM staging.stg_dim_airlines
WHERE airline_name NOT LIKE 'Blocked%'
;
