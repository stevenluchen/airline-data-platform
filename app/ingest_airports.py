import json
from pathlib import Path
from sqlalchemy import text
from db import get_engine
import requests

AIRPORTS_URL = "https://raw.githubusercontent.com/mwgg/Airports/master/airports.json"


def ingest_airports():
    engine = get_engine()

    response = requests.get(AIRPORTS_URL, timeout=30)
    response.raise_for_status()
    airports = response.json()

    rows = []
    for icao, airport in airports.items():
        rows.append({
            "airport_icao": icao,
            "airport_iata": airport.get("iata"),
            "airport_name": airport.get("name"),
            "city": airport.get("city"),
            "country": airport.get("country"),
            "elevation_ft": airport.get("elevation"),
            "latitude": airport.get("lat"),
            "longitude": airport.get("lon"),
            "timezone": airport.get("tz"),
        })

    insert_sql = text("""
        INSERT INTO analytics.dim_airports (
            airport_icao,
            airport_iata,
            airport_name,
            city,
            country,
            elevation_ft,
            latitude,
            longitude,
            timezone
        )
        VALUES (
            :airport_icao,
            nullif(:airport_iata, ''),
            nullif(:airport_name, ''),
            nullif(:city, ''),
            nullif(:country, ''),
            :elevation_ft,
            :latitude,
            :longitude,
            :timezone
        )
        ON CONFLICT (airport_icao) DO UPDATE SET
            airport_iata = EXCLUDED.airport_iata,
            airport_name = EXCLUDED.airport_name,
            city = EXCLUDED.city,
            country = EXCLUDED.country,
            elevation_ft = EXCLUDED.elevation_ft,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            timezone = EXCLUDED.timezone;
    """)

    with engine.begin() as conn:
        conn.execute(insert_sql, rows)

    print(f"Loaded {len(rows):,} airports into analytics.dim_airports")


if __name__ == "__main__":
    ingest_airports()