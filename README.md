## Current Architecture

OpenSky API → Python ingestion → PostgreSQL raw layer

## Running locally

docker compose up -d

`python app/ingest.py` to pull latest OpenSky state vectors

## Current Tables

raw.state_vectors
raw.airframe_history

analytics.dim_aircraft
analytics.dim_aircraft_types
analytics.dim_airlines

## Next steps

Set up recurring job on `ingest.py`

Set up recurring updates on `dim_aircraft` table, pulling from [OpenAirframes](https://github.com/PlaneQuery/OpenAirframes)

Define join logic for state vectors with airline, aircraft, and aircraft type.

Finalize plans for how to handle general aviation and non-commercial callsigns.

Currently, all table definitions and transformations live in `create_tables.sql`. Maybe organize them a bit. 

## Notes/obstacles

7/25: Raw airframes data ingests slowly, adding chunking logic helps. Consider using Postgres bulk loader rather than `pandas.to_sql()`.

7/26: Deduped raw airframes data and removed entries for ambiguous aircraft or those with zero metadata, significantly reducing cardinality. Set up raw/staging/analytics schemas for future changes.