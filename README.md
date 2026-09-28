# Airline Data Platform

A batch data pipeline that ingests live aircraft position data from the [OpenSky Network API](https://opensky-network.org), enriches it with aircraft and airline reference data, and serves it as analytics-ready tables in PostgreSQL. Orchestrated with Airflow on a 10-minute cadence.

## Architecture

```
OpenSky API ──► Python ingestion ──► raw ──► staging ──► analytics
  (OAuth2)        (Airflow, 10m)      ▲         ▲            ▲
                                      │         │            │
OpenAirframes ──► bulk load ──────────┘         │            │
avcodes.co.uk ──► CSV ingest ──────────────────┘            │
mwgg/Airports ──► JSON ingest ──────────────────────────────┘
```

**Layer conventions (medallion):**

| Schema | Purpose |
|---|---|
| `raw` | Unmodified source data, one table per source. Never mutated by transforms. |
| `staging` | Lightly cleaned copies of raw reference data (trimming, parsing, type fixes). Rebuilt from scratch each run. |
| `analytics` | Enriched fact and dimension tables for downstream queries and dashboards. |

## Pipeline flow

Each scheduled run of the `airline_data_ingest` DAG:

1. **Fetch** — pulls the latest state vectors from OpenSky (`/states/all`) using OAuth2 client credentials.
2. **Ingest** — stamps the batch with a `snapshot_id` and inserts rows into `raw.state_vectors`.
3. **Transform** — `transform_snapshot(snapshot_id)` joins that snapshot to `dim_airlines` (via the ICAO callsign prefix) and `dim_aircraft` (via `icao24`), then upserts into `analytics.fact_aircraft_positions`.

Design notes:

- Raw ingestion and transformation are separate steps: if the transform fails, the raw snapshot is preserved and can be reprocessed.
- Reprocessing a snapshot is idempotent — `ON CONFLICT (snapshot_id, icao24, api_time) DO NOTHING` guarantees no duplicates.
- All writes run inside transactions (`engine.begin()`).

## Prerequisites

- Docker + Docker Compose
- An [OpenSky Network](https://opensky-network.org) account with an API client created (Account page → API Client). Anonymous access is limited to 400 credits/day, which the 10-minute cadence will exhaust.

## Quickstart

1. Create a `.env` file in the repo root:

```env
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=airline
POSTGRES_USER=airline
POSTGRES_PASSWORD=...

OPENSKY_CLIENT_ID=...
OPENSKY_CLIENT_SECRET=...

AIRFLOW_DB_PASSWORD=...
AIRFLOW_API_JWT_SECRET=...
AIRFLOW_SECRET_KEY=...
```

2. Start everything:

```bash
docker compose up -d
```

This brings up the pipeline Postgres, a dedicated Postgres for Airflow metadata, and the Airflow webserver / scheduler / DAG processor. The Airflow UI is at `http://localhost:8080`.

3. Run a one-off ingestion manually:

```bash
python app/ingest_state_vectors.py
```

This fetches the latest state vectors, loads `raw.state_vectors`, and runs the transform for that snapshot.

## Project structure

```
├── airflow/
│   ├── Dockerfile                  # Airflow image (app/ on PYTHONPATH)
│   └── dags/
│       └── airline_data_ingest.py  # 10-minute ingest + transform DAG
├── app/
│   ├── ingest_state_vectors.py     # OpenSky fetch + raw load (OAuth2, snapshot-scoped)
│   ├── transform_state_vectors.py  # Snapshot transform → fact table (single source of truth for the load query)
│   ├── ingest_airframes.py         # Bulk load of OpenAirframes historical metadata
│   ├── ingest_airlines.py          # Airline reference data (avcodes.co.uk CSV)
│   ├── ingest_aircraft_types.py    # Aircraft type reference (OpenFlights)
│   ├── ingest_airports.py          # Airport reference data (idempotent upsert)
│   ├── db.py                       # SQLAlchemy engine from env vars
│   └── data/
│       └── airlines_ref.csv
├── sql/
│   ├── raw/                        # DDL for raw tables
│   ├── staging/                    # Rebuild scripts for staging tables
│   └── analytics/                  # DDL for dims, fact table, and the cleaned-positions view
├── data_dictionary.md              # Table grains, keys, and column definitions
├── docker-compose.yml
└── Dockerfile                      # Standalone ingestion image
```

## Data model

Core tables (see `data_dictionary.md` for the full reference):

- **`raw.state_vectors`** — one row per aircraft observation per API snapshot. Grain: `snapshot_id + icao24 + api_time`.
- **`analytics.fact_aircraft_positions`** — the same observations enriched with airline and aircraft metadata. This is the table to query.
- **`analytics.dim_aircraft`** — one row per `icao24`, latest known metadata from OpenAirframes history.
- **`analytics.dim_airlines`** — cleaned airline reference (excludes blocked/redacted entries).
- **`analytics.dim_aircraft_types`**, **`analytics.dim_airports`** — reference dimensions.
- **`analytics.vw_aircraft_positions_cleaned`** — view over the fact table that imputes missing callsigns when an aircraft's callsign drops out mid-sequence but the surrounding observations agree (labels each row as `observed`, `bounded_imputation`, or `unavailable`).

## Reference data refresh

Reference tables are ingested on demand, not on the DAG schedule:

```bash
python app/ingest_airframes.py   # OpenAirframes historical dump (large, chunked load)
python app/ingest_airlines.py    # Airline codes
python app/ingest_aircraft_types.py
python app/ingest_airports.py
```

Then rebuild the derived tables in dependency order:

```bash
psql $DATABASE_URL -f sql/staging/stg_dim_airlines.sql
psql $DATABASE_URL -f sql/analytics/dim_airlines.sql
psql $DATABASE_URL -f sql/analytics/dim_aircraft.sql
```

The staging/analytics rebuild scripts are rerunnable (drop + rebuild).

## Roadmap

- Migrate the SQL layer to dbt (models, tests, docs) — the staging/analytics scripts are already shaped like models.
- Add data quality checks: null-rate assertions, per-snapshot row-count anomaly detection.
- Partition `fact_aircraft_positions` and set a retention policy on `raw.state_vectors` (current cadence ≈ 1.4M fact rows/day).
- CI: lint SQL, validate the DAG imports, verify compose config on every push.
- Decide on handling for general-aviation and non-commercial callsigns (currently only ICAO airline prefixes resolve to `dim_airlines`).
- Alerting on DAG/task failure.

## Notes

- OpenSky rate limits are credit-based: a global `/states/all` call costs 4 credits. Authenticated accounts get 4,000 credits/day.
- Attribution: flight data by [The OpenSky Network](https://opensky-network.org).
