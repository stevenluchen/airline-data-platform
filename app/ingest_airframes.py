import pandas as pd
from db import get_engine
from tqdm import tqdm
from sqlalchemy import text

url = "https://github.com/PlaneQuery/OpenAirframes/releases/download/openairframes-2026-10-06-main/openairframes_adsb_2024-01-01_2026-10-05.csv.gz"

cols = [
    "time",
    "icao24",
    "registration_number",
    "type",
    "dbFlags",
    "ownOp",
    "year",
    "desc",
    "aircraft_category"
]

chunks = pd.read_csv(
    url,
    names=cols,
    na_values="\\N",
    chunksize=50_000
)

engine = get_engine()

latest_chunks = []
for chunk in tqdm(chunks, desc="Reading OpenAirframes"):
    chunk["time_parsed"] = chunk["time"]
    chunk = chunk[
        chunk["icao24"].notna()
        & chunk["icao24"].str.len().eq(6)
        & chunk["time_parsed"].notna()
    ]
    chunk = (
        chunk.sort_values("time_parsed", ascending=False)
        .drop_duplicates("icao24", keep="first")
        .drop(columns="time_parsed")
    )
    latest_chunks.append(chunk)

latest = (
    pd.concat(latest_chunks, ignore_index=True)
    .assign(time_parsed=lambda df: pd.to_datetime(df["time"], errors="coerce"))
    .sort_values("time_parsed", ascending=False)
    .drop_duplicates("icao24", keep="first")
    .drop(columns="time_parsed")
)

staging_table = "airframes_history_staging"
create_staging = text(f"""
    DROP TABLE IF EXISTS raw.{staging_table};
    CREATE TABLE raw.{staging_table} (
        time TEXT,
        icao24 TEXT,
        registration_number TEXT,
        type TEXT,
        "dbFlags" TEXT,
        "ownOp" TEXT,
        year TEXT,
        "desc" TEXT,
        aircraft_category TEXT
    );
""")

with engine.begin() as conn:
    conn.execute(create_staging)

latest.to_sql(
    staging_table,
    engine,
    schema="raw",
    if_exists="append",
    index=False,
    method="multi",
)

# Swap only after the complete snapshot has loaded successfully.
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS raw.airframes_history;"))
    conn.execute(text(f"ALTER TABLE raw.{staging_table} RENAME TO airframes_history;"))

print(f"Loaded {len(latest):,} latest aircraft records into raw.airframes_history")
