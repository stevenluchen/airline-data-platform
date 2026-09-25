-- sql/staging/stg_dim_airlines.sql
-- Rebuilds the staging copy of the airline reference data with basic
-- cleaning applied. Rerunnable: drops and rebuilds the table each run.
DROP TABLE IF EXISTS staging.stg_dim_airlines;

CREATE TABLE staging.stg_dim_airlines AS
SELECT
    *
FROM raw.airlines_ref;

UPDATE staging.stg_dim_airlines
SET iata = LEFT(iata, 2);

UPDATE staging.stg_dim_airlines
SET name = REGEXP_REPLACE(name, '-', '')
WHERE name ~ ' - .*? - ';

ALTER TABLE staging.stg_dim_airlines
ADD COLUMN airline_name TEXT,
ADD COLUMN airline_country TEXT;

UPDATE staging.stg_dim_airlines
SET airline_name = SPLIT_PART(name, ' - ', 1),
    airline_country = SPLIT_PART(name, ' - ', 2);
