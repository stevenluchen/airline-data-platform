import pandas as pd
from sqlalchemy import create_engine

from db import get_engine

url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/planes.dat"

cols = [
    "name",
    "iata",
    "icao"
]

df = pd.read_csv(
    url,
    names=cols,
    na_values="\\N"
)

engine = get_engine()
df.to_sql(
    "dim_aircraft_types",
    engine,
    schema="analytics",
    if_exists="replace",
    index=False
)