import pandas as pd
from sqlalchemy import create_engine

from db import get_engine

path = "data/airlines_ref.csv"

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