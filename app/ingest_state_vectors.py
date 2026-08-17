import requests
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from db import get_engine
from transform_state_vectors import transform_snapshot

OPEN_SKY_URL = "https://opensky-network.org/api/states/all"
logger = logging.getLogger(__name__)

def fetch_states():
    response = requests.get(
        OPEN_SKY_URL,
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def insert_states(data, engine):
    snapshot_id = str(uuid.uuid4())
    api_time = data["time"]
    states = data["states"]
    ingested_at = datetime.now(timezone.utc)

    logger.info(
        "Inserting snapshot %s with %d aircraft",
        snapshot_id,
        len(states)
    )

    insert_query = text("""
        INSERT INTO raw.state_vectors (
            snapshot_id,
            api_time,
            icao24,
            callsign,
            origin_country,
            time_position,
            last_contact,
            longitude,
            latitude,
            baro_altitude,
            on_ground,
            velocity,
            true_track,
            vertical_rate,
            geo_altitude,
            squawk,
            spi,
            position_source,
            ingested_at
        )
        VALUES (
            :snapshot_id,
            :api_time,
            :icao24,
            :callsign,
            :origin_country,
            :time_position,
            :last_contact,
            :longitude,
            :latitude,
            :baro_altitude,
            :on_ground,
            :velocity,
            :true_track,
            :vertical_rate,
            :geo_altitude,
            :squawk,
            :spi,
            :position_source,
            :ingested_at
        )
    """)

    rows = []
    for state in states:
        rows.append({
            "snapshot_id": snapshot_id,
            "api_time": api_time,

            "icao24": state[0],
            "callsign": state[1],
            "origin_country": state[2],

            "time_position": state[3],
            "last_contact": state[4],

            "longitude": state[5],
            "latitude": state[6],

            "baro_altitude": state[7],
            "on_ground": state[8],

            "velocity": state[9],
            "true_track": state[10],
            "vertical_rate": state[11],

            "geo_altitude": state[13],

            "squawk": state[14],
            "spi": state[15],
            "position_source": state[16],

            "ingested_at": ingested_at
        })

    if rows:
        with engine.begin() as conn:
            conn.execute(insert_query, rows)

    return {
        "snapshot_id": snapshot_id,
        "api_time": api_time,
        "aircraft_count": len(states),
        "ingested_at": ingested_at
    }

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    logger.info("Starting OpenSky state vector ingestion...")
    engine = get_engine()
    data = fetch_states()
    result = insert_states(data, engine)
    logger.info(
        "Ingestion complete: snapshot %s, aircraft=%d",
        result["snapshot_id"],
        result["aircraft_count"]
    )
    transform_snapshot(engine, result["snapshot_id"])
    logger.info("Pipeline complete.")

if __name__ == "__main__":
    main()