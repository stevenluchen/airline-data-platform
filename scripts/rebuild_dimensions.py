from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_engine

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
            conn.exec_driver_sql(
                path.read_text(), execution_options={"no_parameters": True}
            )

    print("Dimension rebuild complete.")

if __name__ == "__main__":
    main()
