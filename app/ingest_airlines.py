import pandas as pd
from sqlalchemy import create_engine

from db import get_engine

url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

cols = [
    "airline_id",
    "name",
    "alias",
    "iata",
    "icao",
    "callsign",
    "country",
    "active"
]

df = pd.read_csv(
    url,
    names=cols,
    na_values="\\N"
)

engine = get_engine()
df.to_sql(
    "dim_airlines",
    engine,
    schema="analytics",
    if_exists="replace",
    index=False
)