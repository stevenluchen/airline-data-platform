CREATE OR REPLACE VIEW analytics.vw_aircraft_positions_cleaned AS
WITH 
-- normalized AS (
--     SELECT
--         id,
--         api_time,
--         icao24,
--         NULLIF(TRIM(callsign), '') AS callsign,
--         origin_country,
--         time_position,
--         last_contact,
--         latitude,
--         longitude,
--         baro_altitude,
--         on_ground,
--         velocity,
--         true_track,
--         vertical_rate,
--         sensors,
--         geo_altitude,
--         squawk,
--         spi,
--         position_source,
--         category,
--         ingested_at,
--         snapshot_id
--     FROM analytics.fact_aircraft_positions
-- ),

ordered AS (
    SELECT
        *,
        SUM(
            CASE
                WHEN callsign IS NOT NULL THEN 1
                ELSE 0
            END
        ) OVER (
            PARTITION BY icao24
            ORDER BY api_time
        ) AS callsign_group
    FROM analytics.fact_aircraft_positions
),

null_runs AS (
    SELECT
        icao24,
        callsign_group
    FROM ordered
    WHERE callsign IS NULL
    GROUP BY icao24, callsign_group
),

bounded_runs AS (
    SELECT
        n.icao24,
        n.callsign_group,
        prev.callsign AS imputed_callsign
    FROM null_runs n
    JOIN ordered prev
        ON prev.icao24 = n.icao24
        AND prev.callsign_group = n.callsign_group
    JOIN ordered next_row
        ON next_row.icao24 = n.icao24
        AND next_row.callsign_group = n.callsign_group + 1
    WHERE prev.callsign IS NOT NULL
      AND prev.callsign = next_row.callsign
),

sequence_status as (
    select
        icao24,
        count(*) filter (where callsign is not null) as observed_callsigns
    from analytics.fact_aircraft_positions
    group by icao24
)

SELECT
    aircraft_position_id,
    snapshot_id,
    api_time,
    observed_at,
    o.icao24,
    coalesce(b.imputed_callsign, o.callsign) AS callsign,
    case
        when o.callsign is not null then 'observed'
        when b.imputed_callsign is not null then 'bounded_imputation'
        when s.observed_callsigns = 0 then 'unavailable'
        else null
    END AS callsign_source,
    origin_country,
    airline_icao,
    airline_iata,
    airline_name,
    airline_country,
    aircraft_registration_number,
    aircraft_type,
    aircraft_type_description,
    aircraft_category,
    aircraft_registered_year,
    longitude,
    latitude,
    baro_altitude,
    geo_altitude,
    on_ground,
    velocity,
    true_track,
    vertical_rate,
    squawk,
    spi,
    position_source,
    category,
    ingested_at
FROM ordered o
LEFT JOIN bounded_runs b
    ON b.icao24 = o.icao24
    AND b.callsign_group = o.callsign_group
JOIN sequence_status s
    ON s.icao24 = o.icao24
order by 1;