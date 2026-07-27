import pandas as pd
from db import get_engine
from tqdm import tqdm

url = "https://github.com/PlaneQuery/OpenAirframes/releases/download/openairframes-2026-07-25-develop/openairframes_adsb_2024-01-01_2026-07-24.csv.gz"

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

for chunk in tqdm(chunks):
    chunk.to_sql(
        "aircraft_reference",
        engine,
        schema="public",
        if_exists="append",
        index=False,
        method="multi"
    )