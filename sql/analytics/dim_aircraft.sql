-- sql/analytics/dim_aircraft.sql
DROP TABLE IF EXISTS analytics.dim_aircraft;

CREATE TABLE analytics.dim_aircraft AS
SELECT
    icao24,
    registration_number,
    "type",
    "desc",
    "ownOp" AS operator,
    case when "year" = '0' then null else "year" end,
    aircraft_category,
    time::TIMESTAMP AS last_updated
FROM raw.airframes_history
WHERE length(icao24) = 6;
