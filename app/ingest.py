import requests
import uuid
from datetime import datetime, timezone
from sqlalchemy import text

from db import get_engine

OPEN_SKY_URL = "https://opensky-network.org/api/states/all"

def fetch_states():
    response = requests.get(
        OPEN_SKY_URL,
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def insert_states(data):
    engine = get_engine()
    snapshot_id = str(uuid.uuid4())
    api_time = data["time"]
    states = data["states"]
    print(f"Snapshot: {snapshot_id}")
    print(f"Aircraft found: {len(states)}")

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

            "ingested_at": datetime.now(timezone.utc)
        })

    with engine.begin() as conn:
        conn.execute(insert_query, rows)

def main():
    print("Fetching OpenSky data...")
    data = fetch_states()
    insert_states(data)
    print("Done!")

if __name__ == "__main__":
    main()