import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import requests
from sqlalchemy import text

from db import get_engine
from transform_state_vectors import transform_snapshot

OPEN_SKY_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol"
    "/openid-connect/token"
)
logger = logging.getLogger(__name__)

# Cached bearer token, refreshed proactively before expiry
_token_cache = {"token": None, "expires_at": 0.0}


def _get_access_token():
    """Fetch an OAuth2 access token via client credentials flow.

    Returns None when OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET are not set,
    in which case requests fall back to anonymous access (tight rate limits).
    """
    client_id = os.getenv("OPENSKY_CLIENT_ID")
    client_secret = os.getenv("OPENSKY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    _token_cache["token"] = payload["access_token"]
    _token_cache["expires_at"] = now + payload.get("expires_in", 1800)
    logger.info("Fetched new OpenSky access token")
    return _token_cache["token"]


def fetch_states():
    headers = {}
    token = _get_access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning(
            "OPENSKY_CLIENT_ID/OPENSKY_CLIENT_SECRET not set; using anonymous "
            "access (400 credits/day -- the 10-minute cadence will be rate limited)"
        )

    response = requests.get(OPEN_SKY_URL, headers=headers, timeout=30)
    if response.status_code == 401 and token:
        # Token may have expired between the cache check and the request;
        # refresh once and retry.
        _token_cache["token"] = None
        headers["Authorization"] = f"Bearer {_get_access_token()}"
        response = requests.get(OPEN_SKY_URL, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def insert_states(data, engine):
    snapshot_id = str(uuid.uuid4())
    api_time = data["time"]
    states = data["states"]
    ingested_at = datetime.now(timezone.utc).replace(second=0, microsecond=0)

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
            sensors,
            geo_altitude,
            squawk,
            spi,
            position_source,
            category,
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
            :sensors,
            :geo_altitude,
            :squawk,
            :spi,
            :position_source,
            :category,
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

            "sensors": json.dumps(state[12]) if state[12] is not None else None,

            "geo_altitude": state[13],

            "squawk": state[14],
            "spi": state[15],
            "position_source": state[16],
            "category": state[17],

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
