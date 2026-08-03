-- sql/populate_dim_aircraft.sql
CREATE table if not exists analytics.dim_aircraft AS
SELECT
    icao24,
    registration_number,
    "type",
    "desc",
    "ownOp" AS operator,
    case when "year" = '0' then null else "year" end,
    aircraft_category,
    time::TIMESTAMP AS last_updated
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY icao24
            ORDER BY time DESC
        ) AS rn
    FROM raw.airframes_history
    WHERE length(icao24) = 6
) 
WHERE rn = 1;
