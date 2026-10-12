from pathlib import Path
from app.db import get_engine

ROOT = Path(__file__).resolve().parents[1]

SQL_FILES = [
    "sql/staging/stg_dim_airlines.sql",
    "sql/analytics/dim_airlines.sql",
    "sql/analytics/dim_aircraft.sql",
]

def main():
    engine = get_engine()

    with engine.begin() as conn:
        for relative_path in SQL_FILES:
            path = ROOT / relative_path
            print(f"Applying {relative_path}")
            conn.exec_driver_sql(path.read_text())

    print("Dimension rebuild complete.")

if __name__ == "__main__":
    main()
