import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

from db import get_engine

path = Path(__file__).resolve().parent / "data" / "airlines_ref.csv"

cols = [
    "icao",
    "iata",
    "name",
    "icao_callsign"
]

df = pd.read_csv(
    path,
    names=cols,
    na_values="\\N"
)

engine = get_engine()
df.to_sql(
    "airlines_ref",
    engine,
    schema="raw",
    if_exists="replace",
    index=False
)