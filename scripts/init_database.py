from pathlib import Path
from sqlalchemy import text
from app.db import get_engine

ROOT = Path(__file__).resolve().parents[1]

SQL_FILES = [
    "sql/raw/state_vectors.sql",
    "sql/raw/airlines_ref.sql",
    "sql/raw/airframes_history.sql",
    "sql/analytics/dim_aircraft_types.sql",
    "sql/analytics/dim_airports.sql",
    "sql/analytics/fact_aircraft_positions.sql",
    "sql/analytics/vw_aircraft_positions_cleaned.sql",
]

def main():
    engine = get_engine()

    with engine.begin() as conn:
        for schema in ("raw", "staging", "analytics"):
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

        for relative_path in SQL_FILES:
            path = ROOT / relative_path
            print(f"Applying {relative_path}")
            conn.exec_driver_sql(path.read_text())

    print("Database initialization complete.")

if __name__ == "__main__":
    main()
