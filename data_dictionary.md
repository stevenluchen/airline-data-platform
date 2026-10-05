# Airline Data Platform — Data Dictionary

This document describes the tables and view currently defined by the SQL files and populated by the application code.

## `raw.state_vectors`.

**Purpose:** Raw aircraft state observations returned by the OpenSky `/states/all` API.

**Grain:** One row per aircraft (`icao24`) in an ingestion snapshot. The intended natural key is `(snapshot_id, icao24, api_time)`.

**Physical key:** `id BIGSERIAL PRIMARY KEY`.

**Load behavior:** `app/ingest_state_vectors.py` inserts a new UUID `snapshot_id` and appends rows. There is no database unique constraint on the raw table.

Columns include `snapshot_id`, `api_time`, `icao24`, `callsign`, `origin_country`, `time_position`, `last_contact`, `longitude`, `latitude`, `baro_altitude`, `on_ground`, `velocity`, `true_track`, `vertical_rate`, `sensors`, `geo_altitude`, `squawk`, `spi`, `position_source`, `category`, and `ingested_at`.

`sensors` is defined as `JSONB` but is not currently populated by ingestion. Timestamps from the API are stored as Unix seconds in `BIGINT` fields; `ingested_at` is a `TIMESTAMP` rounded to the minute by the ingestion script.

## `raw.airframes_history`

**Purpose:** Historical aircraft metadata from the OpenAirframes compressed CSV export.

**Grain:** One metadata record per aircraft and source timestamp.

**Physical key:** None declared.

**Load behavior:** `app/ingest_airframes.py` appends 50,000-row chunks. Re-running it can duplicate source records unless the target is cleared first.

Columns are `time`, `icao24`, `registration_number`, `type`, `dbFlags`, `ownOp`, `year`, `desc`, and `aircraft_category`, all defined as `TEXT`.

## `raw.airlines_ref`

**Purpose:** Raw airline reference data bundled at `app/data/airlines_ref.csv`.

**Grain:** One airline reference row.

**Physical key:** None declared.

**Load behavior:** `app/ingest_airlines.py` loads the CSV with `if_exists="replace"`.

Columns are `icao`, `iata`, `name`, and `icao_callsign`, all `TEXT`.

## `staging.stg_dim_airlines`

**Purpose:** Cleaned and parsed copy of `raw.airlines_ref`.

**Grain:** One row per source airline record; no key is declared.

**Load behavior:** Dropped and recreated by `sql/staging/stg_dim_airlines.sql`.

The original columns are retained. `iata` is truncated to two characters; `name` is cleaned; and the transformation adds `airline_name` and `airline_country`, derived by splitting `name` on ` - `.

## `analytics.dim_airlines`

**Purpose:** Analytics-ready airline lookup used to enrich callsigns.

**Grain:** One row per retained staging airline record.

**Physical key:** None declared, despite `icao` functioning as the intended business key.

**Load behavior:** Dropped and recreated from staging. Rows whose `airline_name` starts with `Blocked` are excluded.

Columns are `icao`, `iata`, `airline_name`, `airline_country`, and `callsign` (sourced from `icao_callsign`). The fact transformation joins this table using the first three characters of the normalized callsign against `icao`.

## `analytics.dim_aircraft`

**Purpose:** Latest known aircraft metadata for enrichment.

**Grain:** One row per valid six-character `icao24`.

**Physical key:** None declared; `icao24` is the intended business key.

**Load behavior:** Dropped and rebuilt from `raw.airframes_history`. A window function selects the record with the greatest `time` per `icao24`.

Columns are `icao24`, `registration_number`, `type`, `desc`, `operator`, `year`, `aircraft_category`, and `last_updated`. `year` is converted to null when the source value is `'0'`.

## `analytics.dim_aircraft_types`

**Purpose:** Aircraft type lookup from OpenFlights `planes.dat`.

**Grain:** One row per source aircraft type record.

**Physical key:** None declared.

**Load behavior:** `app/ingest_aircraft_types.py` replaces the table on each run.

Columns are `name`, `iata`, and `icao`, all `TEXT`. This table is currently not joined by the state-vector transformation; aircraft metadata is sourced from `dim_aircraft` instead.

## `analytics.dim_airports`

**Purpose:** Airport reference dimension from the mwgg/Airports JSON dataset.

**Grain:** One row per airport ICAO code.

**Physical key:** `airport_icao VARCHAR(4) PRIMARY KEY`.

**Load behavior:** `app/ingest_airports.py` performs an insert/upsert on `airport_icao`.

Columns include ICAO/IATA codes, airport name, city, country, elevation, latitude, longitude, and timezone. Numeric geographic fields are `DOUBLE PRECISION`; elevation is `INTEGER`.

## `analytics.fact_aircraft_positions`

**Purpose:** Enriched aircraft observations for analytics and dashboards.

**Grain:** One row per aircraft observation per API snapshot.

**Physical key:** `aircraft_position_id BIGSERIAL PRIMARY KEY`.

**Natural uniqueness:** Unique index on `(snapshot_id, icao24, api_time)`.

**Load behavior:** `app/transform_state_vectors.py` inserts rows from one raw snapshot, joins `dim_airlines` and `dim_aircraft`, and uses `ON CONFLICT DO NOTHING` for idempotent reprocessing.

The table contains snapshot/timestamp fields, aircraft and airline enrichment fields, position and flight-state measures, operational metadata, and `ingested_at`. `observed_at` is derived from `api_time` with `TO_TIMESTAMP`.

Airline enrichment can be null when a callsign does not match `dim_airlines`; aircraft enrichment can be null when `icao24` is absent from `dim_aircraft`.

## `analytics.vw_aircraft_positions_cleaned`

**Purpose:** Consumer-facing view over the fact table with callsign quality labeling.

For each aircraft, the view identifies null-callsign runs bounded by matching non-null callsigns and fills those runs with the matching callsign.

`callsign_source` is `observed` for an original callsign, `bounded_imputation` for a filled bounded null run, `unavailable` when the aircraft has no observed callsign anywhere in the fact table, and `NULL` for other unclassified null callsigns.

The view otherwise exposes the fact-table attributes and orders results by `aircraft_position_id`.

## Operational gaps reflected by the current implementation

- No schema bootstrap or database migration runner is included.
- No primary or unique keys are declared on the airline, aircraft, aircraft-type, or raw history dimensions beyond the keys noted above.
- Reference-data refreshes are manual and are not part of the Airflow DAG.
- The raw `sensors` field is defined but not loaded.
- No automated row-count, null-rate, freshness, or referential-integrity checks are defined.
