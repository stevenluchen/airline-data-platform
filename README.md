## Current Architecture

OpenSky API → Python ingestion → PostgreSQL raw layer

## Running locally

docker compose up -d

`python app/ingest_state_vectors.py` to pull the latest OpenSky state vectors
and load them into `analytics.fact_aircraft_positions`.

Recurring ingestion runs on a 10-minute schedule via the Airflow DAG in
`airflow/dags/airline_data_ingest.py` (see `docker-compose.yml` for the
Airflow webserver/scheduler services).

### OpenSky authentication

OpenSky retired anonymous and basic-auth access; the API now requires OAuth2
client credentials. Create an API client at
[opensky-network.org](https://opensky-network.org) (Account page) and add the
credentials to your `.env`:

```
OPENSKY_CLIENT_ID=...
OPENSKY_CLIENT_SECRET=...
```

Without them, ingestion falls back to anonymous access (400 credits/day),
which the 10-minute cadence will exhaust and rate-limit.

Airflow runs its own metadata database (separate from the pipeline
database), configured with:

```
AIRFLOW_DB_PASSWORD=...
```

## Current Tables

raw.state_vectors

raw.airframe_history

raw.airlines_ref

staging.stg_dim_airlines

analytics.dim_aircraft

analytics.dim_aircraft_types

analytics.dim_airlines

analytics.fact_aircraft_positions

## Ingestion automation and validation

Each run of `ingest_state_vectors.py`:

1. Pulls OpenSky state vectors

2. Creates a `snapshot_id`

3. Stores raw data in `raw.state_vectors`

4. Transforms only that snapshot

5. Enriches with dimension tables

6. Loads into `analytics.fact_aircraft_positions`

### Notes

* Centralized logging using `logging` module

* Separation of raw ingestion and transformation: `raw.state_vectors` -> `transform_snapshot(snapshot_id)` -> `analytics.fact_aircraft_positions`. Successful ingestion will not disappear if downstream transformation fails. 

* Calling `engine.begin()` ensures transaction-safe execution

### Idempotency

Reprocessing the same snapshot produces no duplicates due to the `ON CONFLICT` clause in the query. `(snapshot_id, icao24, api_time)` servics as composite uniqueness constraint. 

## Next steps

Set up recurring updates on `dim_aircraft` table, pulling from [OpenAirframes](https://github.com/PlaneQuery/OpenAirframes)

Finalize plans for how to handle general aviation and non-commercial callsigns.

Read about incremental loading, data quality checks, and tests. What are the softwares/tools needed for these?

Update data dictionary placeholder values

Partition `fact_aircraft_positions` / set a retention policy on `raw.state_vectors` before volume becomes a problem (~1.4M fact rows/day at the current cadence)

## Notes/obstacles

7/25: Raw airframes data ingests slowly, adding chunking logic helps. Consider using Postgres bulk loader rather than `pandas.to_sql()`.

7/26: Deduped raw airframes data and removed entries for ambiguous aircraft or those with zero metadata, significantly reducing cardinality. Set up raw/staging/analytics schemas for future changes.

8/3: Changed airlines reference table source as previous one was out of date and incomplete. Created data dictionary, organized SQL table definitions and Postgres schema. 

8/16: Finalized ETL layer and preparing for automation