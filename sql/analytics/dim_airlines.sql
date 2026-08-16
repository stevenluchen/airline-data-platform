CREATE TABLE IF NOT EXISTS analytics.dim_airlines AS
SELECT
    icao,
    iata,
    airline_name,
    airline_country,
    icao_callsign as callsign
FROM staging.stg_dim_airlines
WHERE airline_name NOT LIKE 'Blocked%'
;