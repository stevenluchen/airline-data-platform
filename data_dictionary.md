# Data Dictionary

This document summarizes the main tables in the project schema, including their purpose, grain, keys, and source context.

## Table Overview

| Table | Schema | Purpose | Source |
| --- | --- | --- | --- |
| raw.state_vectors | raw | Raw OpenSky aircraft state snapshots | OpenSky Network API |
| raw.airframes_history | raw | Historical aircraft metadata reference records | OpenAirframes dataset |
| raw.airlines_ref | raw | Raw airline reference records | avcodes.co.uk |
| analytics.dim_aircraft | analytics | Deduped aircraft dimension table | OpenAirframes + transformation logic |
| analytics.dim_aircraft_types | analytics | Aircraft type reference dimension | OpenFlights planes data |
| analytics.dim_airlines | analytics | Airline reference dimension | avcodes.co.uk + staging transformation |
| staging.stg_dim_airlines | staging | Staging copy of airline reference data with cleaning/transformation applied | avcodes.co.uk |
| analytics.fact_aircraft_positions | analytics | Enriched aircraft observation fact table | raw.state_vectors + airline + aircraft dimensions |

## 1. raw.state_vectors

### Purpose
Represents a raw snapshot of aircraft state observations collected from the OpenSky Network API.

### Grain
One row per aircraft state observation within a single API snapshot.

### Primary / Unique Keys
- Primary key: id (auto-incrementing serial)
- Unique constraint: TBD
- Suggested natural key candidate: snapshot_id + icao24 + api_time + last_contact

### Source
- Source system: OpenSky Network states API
- Ingestion path: app/ingest_state_vectors.py

### Key columns
- snapshot_id: identifier for the ingestion batch/snapshot
- api_time: timestamp from the API response
- icao24: aircraft ICAO 24-bit address
- callsign, origin_country: aircraft identification metadata
- longitude, latitude, velocity, vertical_rate: live state fields
- ingested_at: load timestamp

---

## 2. raw.airframes_history

### Purpose
Stores historical aircraft metadata records imported from the OpenAirframes reference dataset.

### Grain
One row per aircraft metadata record at a given historical timestamp.

### Primary / Unique Keys
- Primary key: TBD
- Unique constraint: TBD
- Suggested natural key candidate: icao24 + time

### Source
- Source system: OpenAirframes historical aircraft metadata export
- Ingestion path: app/ingest_airframes.py

### Key columns
- time: source timestamp for the record
- icao24: aircraft identifier
- registration_number: aircraft registration number
- type, desc, aircraft_category: aircraft metadata
- ownOp, year: operator and manufacturing year

---

## 3. analytics.dim_aircraft

### Purpose
A deduplicated dimension table for aircraft, intended to provide one row per aircraft identifier.

### Grain
One row per unique aircraft, keyed by icao24.

### Primary / Unique Keys
- Primary key: icao24
- Unique constraint: effectively one row per icao24

### Source
- Source system: raw.airframes_history
- Transformation: populated by selecting the latest record per icao24 from the historical airframes data
- Ingestion path: SQL load logic in sql/staging/stg_dim_aircraft.sql

### Key columns
- icao24: surrogate/business key for the aircraft
- registration_number: registration identifier
- type, desc: aircraft type and description
- operator, year, aircraft_category: descriptive attributes
- last_updated: timestamp of most recent source record used

---

## 4. analytics.dim_aircraft_types

### Purpose
Reference table for aircraft types used in downstream analytics and joins.

### Grain
One row per aircraft type reference entry.

### Primary / Unique Keys
- Primary key: TBD
- Unique constraint: TBD

### Source
- Source system: OpenFlights planes data
- Ingestion path: app/ingest_aircraft_types.py

### Key columns
- name: aircraft type name
- iata: IATA code
- icao: ICAO code

---

## 5. raw.airlines_ref

### Purpose
Stores the raw airline reference records imported from avcodes.co.uk.

### Grain
One row per airline reference record.

### Primary / Unique Keys
- Primary key: TBD
- Unique constraint: TBD
- Suggested natural key candidate: icao

### Source
- Source system: avcodes.co.uk airline code reference data
- Ingestion path: TBD

### Key columns
- icao: airline ICAO code
- iata: airline IATA code
- name: airline name as provided by the source
- icao_callsign: ICAO-style callsign value

---

## 6. staging.stg_dim_airlines

### Purpose
A staging table that mirrors raw.airlines_ref and applies basic cleaning and parsing so the analytics table is easier to consume.

### Grain
One row per airline reference record.

### Primary / Unique Keys
- Primary key: TBD
- Unique constraint: TBD

### Source
- Source system: raw.airlines_ref
- Transformation logic: trims IATA values to two characters, removes formatting from names, splits names into airline_name and airline_country, and creates the analytics-ready columns

### Key columns
- icao, iata, name, icao_callsign: raw staging values
- airline_name: extracted airline name
- airline_country: extracted country from the source name

---

## 7. analytics.dim_airlines

### Purpose
A cleaned airline dimension table for downstream analytics and joins.

### Grain
One row per airline reference record.

### Primary / Unique Keys
- Primary key: TBD
- Unique constraint: TBD

### Source
- Source system: staging.stg_dim_airlines
- Transformation logic: built from the staging table and excludes entries where airline_name starts with 'Blocked'

### Key columns
- icao: airline ICAO code
- iata: trimmed IATA code
- airline_name: cleaned airline name
- airline_country: cleaned country name
- callsign: ICAO callsign value

---

## 8. analytics.fact_aircraft_positions

### Purpose
A denormalized fact table that enriches each raw OpenSky position observation with aircraft and airline metadata for analytics and dashboard use.

### Grain
One row per aircraft observation at a given snapshot time.

### Primary / Unique Keys
- Primary key: aircraft_position_id (surrogate key)
- Recommended natural key: snapshot_id + icao24 + api_time
- Unique index: recommended on (snapshot_id, icao24, api_time)

### Source
- Source systems: raw.state_vectors, analytics.dim_aircraft, analytics.dim_airlines
- Transformation logic: joins the raw state vectors to airline and aircraft dimension tables and retains the enriched payload for downstream analysis

### Key columns
- aircraft_position_id: surrogate key for the fact row
- snapshot_id: OpenSky snapshot identifier
- api_time / observed_at: observation timestamp
- icao24: aircraft identifier
- callsign, origin_country: flight and origin metadata
- airline_icao, airline_iata, airline_name, airline_country: airline enrichment fields
- aircraft_registration_number, aircraft_type, aircraft_type_description, aircraft_category, aircraft_registered_year: aircraft enrichment fields
- longitude, latitude, baro_altitude, geo_altitude, on_ground, velocity, true_track, vertical_rate: flight-state metrics
- squawk, spi, position_source, category: operational metadata
- ingested_at: row load timestamp

---

## 9. staging logic note

### stg_dim_aircraft
This SQL script is not a physical table definition; it is a transformation step that loads the analytics.dim_aircraft dimension from raw.airframes_history.

### Grain / Keys
- Grain: one row per latest record for each icao24
- Primary key: inherited from analytics.dim_aircraft (icao24)
- Source: raw.airframes_history

### fact_aircraft_positions
This table is a materialized analytics fact table intended to be refreshed after the base ingest jobs run. It is designed to support dashboards, operational queries, and enriched flight-state analysis.
