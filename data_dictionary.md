# Airline Data Platform — Data Dictionary

This document describes the tables, view, and dashboard-facing query behavior currently defined by the SQL files and application code.

## `raw.state_vectors`

**Purpose:** Raw aircraft state observations returned by the OpenSky `/states/all` API.

**Grain:** One row per aircraft (`icao24`) in an ingestion snapshot. The intended natural key is `(snapshot_id, icao24, api_time)`.

**Physical key:** `id BIGSERIAL PRIMARY KEY`.

**Load behavior:** `app/ingest_state_vectors.py` inserts a new UUID `snapshot_id` and appends rows. There is no database unique constraint on the raw table.

Columns include `snapshot_id`, `api_time`, `icao24`, `callsign`, `origin_country`, `time_position`, `last_contact`, `longitude`, `latitude`, `baro_altitude`, `on_ground`, `velocity`, `true_track`, `vertical_rate`, `sensors`, `geo_altitude`, `squawk`, `spi`, `position_source`, `category`, and `ingested_at`.

`sensors` is defined as `JSONB` but is not currently populated by ingestion. Timestamps from the API are stored as Unix seconds in `BIGINT` fields; `ingested_at` is a `TIMESTAMP` rounded to the minute by the ingestion script.

## `raw.airframes_history`

**Purpose:** Current aircraft metadata distilled from the OpenAirframes historical CSV export.

**Grain:** One latest metadata record per valid six-character `icao24`.

**Physical key:** None declared.

**Load behavior:** `app/ingest_airframes.py` reads the historical source in chunks, retains the newest record per `icao24`, loads a staging table, and swaps it into place after a successful load. Re-running the script replaces the snapshot rather than appending duplicates.

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

## `staging.stg_airframes_history`

**Purpose:** Temporary latest-aircraft snapshot used during the OpenAirframes refresh.

**Grain:** One candidate row per valid six-character `icao24`.

**Physical key:** None declared.

**Load behavior:** Dropped and recreated from `sql/staging/stg_airframes_history.sql`, populated by `app/ingest_airframes.py`, validated for non-empty unique `icao24` values, then promoted to `raw.airframes_history`. It is not intended to remain as a long-term historical table.

## `analytics.dim_airlines`

**Purpose:** Analytics-ready airline lookup used to enrich callsigns.

**Grain:** One row per retained staging airline record.

**Physical key:** None declared, despite `icao` functioning as the intended business key.

**Load behavior:** Dropped and recreated from staging. Rows whose `airline_name` starts with `Blocked` are excluded.

Columns are `icao`, `iata`, `airline_name`, `airline_country`, and `callsign` (sourced from `icao_callsign`). The fact transformation joins this table using the first three characters of the normalized callsign against `icao`.

## `analytics.dim_aircraft`

**Purpose:** Aircraft metadata for enrichment.

**Grain:** One row per valid six-character `icao24`.

**Physical key:** None declared; `icao24` is the intended business key.

**Load behavior:** Dropped and rebuilt from the already-deduplicated `raw.airframes_history` snapshot.

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

## Streamlit dashboard query layer

The dashboard is implemented in `app/app.py` and does not create additional database tables or views.

**Primary source:** `analytics.fact_aircraft_positions` is queried directly for dashboard performance. The dashboard does not currently use `analytics.vw_aircraft_positions_cleaned`.

**Time grain:** `ingested_at`, which represents the approximately five-minute ingestion bucket. The selected date is filtered using `ingested_at` and the map slider advances through available five-minute buckets.

**Map aggregate:** Airborne rows (`on_ground IS FALSE`) are filtered to the selected geographic region and grouped into latitude/longitude grid cells. The grid width changes by region to provide finer detail in compact areas such as Japan and coarser aggregation over large areas such as North America and Global.

**Supporting aggregates:** The dashboard also queries the fact table for distinct airborne aircraft by ingestion bucket and top airlines by distinct airborne aircraft over the selected day and region.

**Hexbin detail query:** Clicking a map cell queries all airborne fact rows matching the selected `ingested_at` bucket and cell coordinates. The result is displayed as an aircraft detail table containing identifiers, callsign and airline fields, aircraft metadata, position, altitude, velocity, and track.

**Caching:** Dashboard aggregate queries are cached for five minutes. Changing the date or region creates a new scoped query.

## Operational gaps reflected by the current implementation

- `scripts/init_database.py` initializes schemas and base tables; it is not a full versioned migration system.
- No primary or unique keys are declared on the airline, aircraft, aircraft-type, or raw history dimensions beyond the keys noted above.
- Airline, aircraft-type, and airport reference refreshes remain manual; the OpenAirframes aircraft refresh is scheduled daily by Airflow at 08:00 UTC.
- The raw `sensors` field is defined but not loaded.
- No automated row-count, null-rate, freshness, or referential-integrity checks are defined.
