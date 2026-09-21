import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

TRANSFORM_QUERY = text("""
    INSERT INTO analytics.fact_aircraft_positions (
        snapshot_id,
        api_time,
        observed_at,
        icao24,
        callsign,
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
    )
    SELECT
        sv.snapshot_id,
        sv.api_time,
        TO_TIMESTAMP(sv.api_time) AS observed_at,
        sv.icao24,
        nullif(sv.callsign, ''),
        sv.origin_country,
        al.icao AS airline_icao,
        al.iata AS airline_iata,
        al.airline_name,
        al.airline_country,
        ac.registration_number AS aircraft_registration_number,
        ac."type" AS aircraft_type,
        ac."desc" AS aircraft_type_description,
        ac.aircraft_category,
        ac.year AS aircraft_registered_year,
        sv.longitude,
        sv.latitude,
        sv.baro_altitude,
        sv.geo_altitude,
        sv.on_ground,
        sv.velocity,
        sv.true_track,
        sv.vertical_rate,
        sv.squawk,
        sv.spi,
        sv.position_source,
        sv.category,
        sv.ingested_at
    FROM raw.state_vectors sv
    LEFT JOIN analytics.dim_airlines al
        ON UPPER(LEFT(sv.callsign, 3)) = UPPER(al.icao)
    LEFT JOIN analytics.dim_aircraft ac
        ON sv.icao24 = ac.icao24
    WHERE sv.snapshot_id = :snapshot_id
    ON CONFLICT (snapshot_id, icao24, api_time) DO NOTHING;
    """)

def transform_snapshot(engine, snapshot_id):
    logger.info("Transforming snapshot %s", snapshot_id)

    with engine.begin() as conn:
        result = conn.execute(
            TRANSFORM_QUERY,
            {"snapshot_id": snapshot_id}
        )

    logger.info(
        "Transformed snapshot %s with %d rows",
        snapshot_id,
        result.rowcount
    )

    return result.rowcount