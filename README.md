# Airline Data Platform

An Airflow-orchestrated ADS-B data pipeline that ingests OpenSky aircraft positions, enriches them with airline and aircraft reference data, and serves analytics-ready PostgreSQL tables to a Streamlit dashboard.

The repository is intentionally local-first: PostgreSQL and Airflow run in Docker, while Streamlit runs locally from the Python environment. No cloud account is required.

## Architecture

```text
OpenSky Network ──► Airflow ──► raw.state_vectors
                                      │
OpenAirframes ────────────────────────┤
Airline / airport references ─────────┤
                                      ▼
                              staging / analytics
                                      │
                                      ▼
                              Streamlit + pydeck
```

The database uses three logical layers:

| Schema | Purpose |
| --- | --- |
| `raw` | Source-shaped tables and ingested snapshots. |
| `staging` | Rebuilt intermediate tables used to clean reference data. |
| `analytics` | Fact, dimension, and consumer-facing view objects. |

## Quickstart

### 1. Clone and configure

```bash
git clone https://github.com/stevenluchen/airline-data-platform.git
cd airline-data-platform
cp .env.example .env
```

Edit `.env` and set at least:

- `POSTGRES_PASSWORD`
- `OPENSKY_CLIENT_ID`
- `OPENSKY_CLIENT_SECRET`
- Airflow passwords and secret values

The example uses `POSTGRES_HOST=localhost` for commands run on the Mac. Docker Compose overrides the host to `postgres` for Airflow containers.

### 2. Start PostgreSQL and Airflow

```bash
docker compose up -d --build
```

The Airflow UI is available at <http://localhost:8080>.

Wait for PostgreSQL to become ready:

```bash
until docker compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; do sleep 2; done
```

If your shell has not loaded `.env`, use the values from `.env` directly in the command or wait a few seconds and retry the next step.

### 3. Initialize the database

```bash
python scripts/init_database.py
```

This creates the `raw`, `staging`, and `analytics` schemas and the base tables, fact table, indexes, and cleaned-position view. It is safe to rerun and does not drop existing base tables.

### 4. Load reference data

Run these once for a fresh database:

```bash
python app/ingest_airlines.py
python app/ingest_aircraft_types.py
python app/ingest_airports.py
python app/ingest_airframes.py
python scripts/rebuild_dimensions.py
```

The OpenAirframes refresh downloads a large historical release but stores only the newest record per aircraft in `raw.airframes_history`. It stages the result, validates it, promotes it atomically, and rebuilds `analytics.dim_aircraft`.

### 5. Start the dashboard

Create a local virtual environment if needed:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

Then run:

```bash
streamlit run app/app.py
```

The dashboard opens at <http://localhost:8501>.

## Streamlit dashboard

The Streamlit app is an interactive “day in the sky” view of the ADS-B data. It is intended to show how aircraft density changes across a selected region during a UTC day, rather than animate individual aircraft trajectories.

The main dashboard includes:

- A UTC date picker.
- A coverage-region selector for North America, Europe, Japan, India, Australia + NZ, and Global.
- A five-minute time slider for scrubbing through the selected day.
- A play/pause time-lapse control that advances through the five-minute buckets.
- A color-coded hexbin density map. Sparse areas use darker colors and dense areas use brighter colors.
- Region-specific bin sizes so compact regions can be viewed at finer resolution.
- Automatic map recentering and zooming when the selected region changes.
- A click interaction for individual hexbins. Selecting a bin displays the aircraft observed in that cell at that time, including callsign, airline, registration, aircraft type, position, altitude, speed, and track.
- A supporting time-series panel showing distinct airborne aircraft over time.
- A supporting ranking panel showing the top airlines by airborne aircraft count.

The map uses aggregate density cells instead of per-aircraft animation. This is intentional: crowdsourced ADS-B coverage is incomplete and uneven, so a missing observation should reduce a cell’s density rather than make an individual aircraft appear to disappear from a trajectory.

The dashboard queries PostgreSQL directly and scopes queries to the selected date, region, and time window. It uses the physical fact table for performance. The cleaned callsign view remains available for consumers that need bounded callsign imputation, but the dashboard currently prioritizes fast aggregate queries over view-based enrichment.

### 6. Run a manual position ingestion

```bash
python app/ingest_state_vectors.py
```

This fetches one OpenSky snapshot, writes it to `raw.state_vectors`, and transforms it into `analytics.fact_aircraft_positions`.

## Scheduled Airflow jobs

### Position ingestion

`airline_data_ingest` runs every five minutes:

```text
fetch OpenSky snapshot
    → insert raw.state_vectors
    → transform snapshot into analytics.fact_aircraft_positions
```

### Airframes reference refresh

`airframe_history_refresh` runs daily at 08:00 UTC, after the OpenAirframes release is expected to be available:

```text
discover latest GitHub release
    → stage and validate latest aircraft rows
    → promote staging snapshot
    → rebuild analytics.dim_aircraft
```

The Airframes DAG uses the current `app/` code and SQL files copied into the Airflow image. Rebuild the Airflow image after changing application or SQL files:

```bash
docker compose build airflow airflow-scheduler airflow-dag-processor
docker compose up -d airflow airflow-scheduler airflow-dag-processor
```

## Project structure

```text
├── .env.example                       # Safe configuration template
├── airflow/
│   ├── Dockerfile                     # Airflow image with app/ and sql/
│   └── dags/
│       ├── airline_data_ingest.py     # Five-minute OpenSky DAG
│       └── airframe_history_refresh.py# Daily 08:00 UTC reference refresh
├── app/
│   ├── app.py                         # Streamlit + pydeck dashboard
│   ├── db.py                          # Environment-based SQLAlchemy engine
│   ├── ingest_airframes.py            # Latest-aircraft snapshot loader
│   ├── ingest_airlines.py             # Airline CSV loader
│   ├── ingest_aircraft_types.py       # OpenFlights aircraft-type loader
│   ├── ingest_airports.py             # Airport upsert loader
│   ├── ingest_state_vectors.py        # OpenSky snapshot loader
│   ├── transform_state_vectors.py     # Snapshot-to-fact transformation
│   ├── requirements.txt                # Python dependencies
│   └── data/airlines_ref.csv           # Bundled airline reference source
├── scripts/
│   ├── init_database.py                # Create schemas and base objects
│   └── rebuild_dimensions.py           # Rebuild staging and derived dimensions
├── sql/
│   ├── raw/                            # Raw table DDL
│   ├── staging/                        # Rebuildable staging SQL
│   └── analytics/                      # Dimensions, fact, and view SQL
├── data_dictionary.md                  # Table grains, columns, keys, and states
├── docker-compose.yml                  # PostgreSQL and Airflow services
├── Dockerfile                          # Standalone ingestion image
└── README.md
```

## Data model

Important objects include:

- `raw.state_vectors`: one row per aircraft observation per OpenSky snapshot.
- `raw.airframes_history`: latest known OpenAirframes record per valid `icao24`; despite the historical source name, it is now a compact current snapshot.
- `raw.airlines_ref`: raw airline reference records.
- `staging.stg_dim_airlines`: cleaned airline reference staging table.
- `staging.stg_airframes_history`: temporary latest-aircraft load before promotion.
- `analytics.dim_aircraft`: current aircraft metadata used for enrichment.
- `analytics.dim_airlines`: cleaned airline dimension.
- `analytics.dim_aircraft_types`: OpenFlights aircraft-type reference.
- `analytics.dim_airports`: airport reference dimension.
- `analytics.fact_aircraft_positions`: enriched aircraft-position fact table.
- `analytics.vw_aircraft_positions_cleaned`: callsign-cleaning view for consumers that need bounded imputation.

See [data_dictionary.md](data_dictionary.md) for detailed grain, key, and load-state documentation.

## Common troubleshooting

### PostgreSQL connection refused

Check that the container is running and ready:

```bash
docker compose ps
docker compose logs postgres
```

For commands run directly on the Mac, use `POSTGRES_HOST=localhost`. Airflow containers use `POSTGRES_HOST=postgres` through the Compose configuration.

### Airflow DAG does not appear

Check the DAG processor logs:

```bash
docker logs airline-airflow-dag-processor
```

After changing `app/` or `sql/`, rebuild the Airflow image and restart the scheduler and DAG processor.

### OpenAirframes refresh is slow

The source release is a large compressed historical CSV. The loader processes it in chunks and retains only one newest row per aircraft. Progress and timing logs identify release discovery, CSV processing, staging insert, validation, promotion, and dimension rebuild phases.

### OpenSky authentication or rate limits

Set valid OAuth2 credentials in `.env`. Authenticated OpenSky access is required for the five-minute schedule.

## Attribution

- Flight data: [The OpenSky Network](https://opensky-network.org)
- Aircraft metadata: [OpenAirframes](https://github.com/PlaneQuery/OpenAirframes)
- Aircraft types: [OpenFlights](https://github.com/jpatokal/openflights)
- Airport data: [mwgg/Airports](https://github.com/mwgg/Airports)
- Airline data: [avcodes.uk](https://www.avcodes.co.uk/)
