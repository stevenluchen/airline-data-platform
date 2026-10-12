import pandas as pd
from db import get_engine
from tqdm import tqdm
from sqlalchemy import text
import requests
from pathlib import Path
import time
import logging

logging.basicConfig(level=logging.INFO)
RELEASES_URL = (
    "https://api.github.com/repos/"
    "PlaneQuery/OpenAirframes/releases"
)
MIN_EXPECTED_ROWS = 100_000
STAGING_TABLE = "stg_airframes_history"


def staging_ddl_path() -> Path:
    path = Path(__file__).resolve().parents[1] / "sql" / "staging" / "stg_airframes_history.sql"
    if not path.exists():
        raise FileNotFoundError(f"Missing staging DDL: {path}")
    return path


def dim_aircraft_sql_path() -> Path:
    path = Path(__file__).resolve().parents[1] / "sql" / "analytics" / "dim_aircraft.sql"
    if not path.exists():
        raise FileNotFoundError(f"Missing aircraft dimension SQL: {path}")
    return path

def get_latest_airframes_url():
    started = time.monotonic()
    logging.info(f"[airframes] Starting GitHub release discovery: {RELEASES_URL}")
    logging.info("[airframes] Sending GitHub API request...")
    response = requests.get(
        RELEASES_URL,
        params={"per_page": 10},
        timeout=30,
    )
    logging.info(
        "[airframes] GitHub response received: "
        f"status={response.status_code}, "
        f"bytes={len(response.content):,}, "
        f"elapsed={time.monotonic() - started:.2f}s",
        extra={"flush": True}
    )
    response.raise_for_status()

    releases = response.json()
    logging.info(f"[airframes] Releases returned: {len(releases)}", extra={"flush": True})

    for release_number, release in enumerate(releases, start=1):
        logging.info(
            f"[airframes] Inspecting release {release_number}: "
            f"tag={release.get('tag_name')!r}, "
            f"published={release.get('published_at')!r}, "
            f"draft={release.get('draft')}, "
            f"prerelease={release.get('prerelease')}, "
            f"assets={len(release.get('assets', []))}",
            extra={"flush": True},
        )
        for asset in release["assets"]:
            name = asset["name"]
            logging.info(f"[airframes]   Checking asset: {name}", extra={"flush": True})
            if name.startswith("openairframes_adsb_") and name.endswith(".csv.gz"):
                url = asset["browser_download_url"]
                logging.info(
                    f"[airframes] Selected asset: {url} "
                    f"(total elapsed={time.monotonic() - started:.2f}s)",
                    extra={"flush": True},
                )
                return url

    logging.info(
        f"[airframes] No matching asset found "
        f"(total elapsed={time.monotonic() - started:.2f}s)",
        extra={"flush": True},
    )
    raise RuntimeError("No OpenAirframes CSV release asset found")

def load_and_validate_staging(url: str) -> dict:
    started = time.monotonic()
    logging.info(f"[airframes] Starting staging load from {url}", extra={"flush": True})

    cols = [
        "time",
        "icao24",
        "registration_number",
        "type",
        "dbFlags",
        "ownOp",
        "year",
        "desc",
        "aircraft_category"
    ]

    chunks = pd.read_csv(
        url,
        names=cols,
        na_values="\\N",
        chunksize=50_000
    )
    logging.info("[airframes] CSV reader initialized; beginning chunk processing", extra={"flush": True})

    engine = get_engine()

    # Keep only one candidate row per aircraft. Accumulating every chunk and
    # concatenating later causes a large memory spike in Airflow.
    latest_by_icao24 = {}
    chunk_count = 0
    source_rows = 0
    candidate_rows = 0
    read_started = time.monotonic()
    for chunk in tqdm(chunks, desc="Reading OpenAirframes"):
        chunk_count += 1
        source_rows += len(chunk)
        chunk["time_parsed"] = chunk["time"]
        chunk = chunk[
            chunk["icao24"].notna()
            & chunk["icao24"].str.len().eq(6)
            & chunk["time_parsed"].notna()
        ]
        chunk = chunk.sort_values("time_parsed", ascending=False).drop_duplicates(
            "icao24", keep="first"
        )
        candidate_rows += len(chunk)
        for row in chunk.itertuples(index=False, name=None):
            icao24 = row[1]
            current = latest_by_icao24.get(icao24)
            if current is None or row[-1] > current[-1]:
                latest_by_icao24[icao24] = row
        if chunk_count % 100 == 0:
            logging.info(
                f"[airframes] Processed {chunk_count:,} chunks, "
                f"source_rows={source_rows:,}, "
                f"chunk_candidates={candidate_rows:,}, "
                f"unique_aircraft={len(latest_by_icao24):,}, "
                f"elapsed={time.monotonic() - read_started:.1f}s",
                extra={"flush": True},
            )

    logging.info(
        f"[airframes] Finished source processing: chunks={chunk_count:,}, "
        f"source_rows={source_rows:,}, candidates={candidate_rows:,}, "
        f"unique_aircraft={len(latest_by_icao24):,}, "
        f"elapsed={time.monotonic() - read_started:.1f}s",
        extra={"flush": True},
    )

    # OpenAirframes timestamps are ISO-formatted, so lexical ordering is
    # chronological and avoids an expensive per-row dateutil parse.
    latest = pd.DataFrame.from_records(
        (row[:-1] for row in latest_by_icao24.values()),
        columns=cols,
    )
    logging.info(
        f"[airframes] Final deduplication complete: "
        f"latest_rows={len(latest):,}, "
        f"elapsed={time.monotonic() - started:.1f}s",
        extra={"flush": True},
    )

    ddl_started = time.monotonic()
    logging.info(f"[airframes] Creating staging table from {staging_ddl_path()}", extra={"flush": True})
    with engine.begin() as conn:
        conn.exec_driver_sql(staging_ddl_path().read_text())
    logging.info(
        f"[airframes] Staging table created in {time.monotonic() - ddl_started:.1f}s",
        extra={"flush": True},
    )

    insert_started = time.monotonic()
    logging.info(f"[airframes] Inserting {len(latest):,} rows into staging", extra={"flush": True})
    latest.to_sql(
        STAGING_TABLE,
        engine,
        schema="staging",
        if_exists="append",
        index=False,
        method="multi",
    )
    logging.info(
        f"[airframes] Staging insert complete in "
        f"{time.monotonic() - insert_started:.1f}s",
        extra={"flush": True},
    )

    validation_started = time.monotonic()
    logging.info("[airframes] Validating staging row counts", extra={"flush": True})
    with engine.connect() as conn:
        row_count, distinct_aircraft = conn.execute(text("""
            SELECT count(*), count(DISTINCT icao24)
            FROM staging.stg_airframes_history
        """)).one()

    if row_count == 0 or row_count != distinct_aircraft:
        raise ValueError(
            "Staging validation failed: expected one non-empty row per icao24 "
            f"but found rows={row_count}, distinct_icao24={distinct_aircraft}"
        )

    if row_count < MIN_EXPECTED_ROWS:
        raise ValueError(
            f"Suspiciously small snapshot: {row_count:,} rows "
            f"(expected at least {MIN_EXPECTED_ROWS:,})"
        )

    logging.info(
        f"[airframes] Staging validated: rows={row_count:,}, "
        f"distinct_icao24={distinct_aircraft:,}, "
        f"elapsed={time.monotonic() - validation_started:.1f}s, "
        f"total={time.monotonic() - started:.1f}s",
        extra={"flush": True},
    )

    return {
        "row_count": row_count,
        "distinct_aircraft": distinct_aircraft,
        "validated": True,
    }

def promote_staging_table():
    started = time.monotonic()
    engine = get_engine()
    logging.info("[airframes] Promoting staging table to raw.airframes_history", extra={"flush": True})

    # Swap only after the complete snapshot has loaded successfully.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS raw.airframes_history;"))
        conn.execute(text(f"ALTER TABLE staging.{STAGING_TABLE} RENAME TO airframes_history;"))
        conn.execute(text("ALTER TABLE staging.airframes_history SET SCHEMA raw;"))

    logging.info(
        f"[airframes] Promotion complete in {time.monotonic() - started:.1f}s",
        extra={"flush": True},
    )


def rebuild_dim_aircraft():
    """Rebuild the aircraft dimension from the current raw snapshot."""
    started = time.monotonic()
    engine = get_engine()
    sql_path = dim_aircraft_sql_path()
    logging.info(f"[airframes] Rebuilding analytics.dim_aircraft from {sql_path}", extra={"flush": True})
    with engine.begin() as conn:
        conn.exec_driver_sql(sql_path.read_text())

    logging.info(
        f"[airframes] Aircraft dimension rebuild complete in "
        f"{time.monotonic() - started:.1f}s",
        extra={"flush": True},
    )


def main():
    started = time.monotonic()
    logging.info("[airframes] Airframes refresh started", extra={"flush": True})
    logging.info("Discovering latest OpenAirframes release...", extra={"flush": True})
    url = get_latest_airframes_url()
    logging.info(f"Selected OpenAirframes asset: {url}", extra={"flush": True})

    result = load_and_validate_staging(url)
    promote_staging_table()
    rebuild_dim_aircraft()
    logging.info(
        "[airframes] Airframes refresh complete: "
        f"{result['row_count']:,} aircraft records, "
        f"total elapsed={time.monotonic() - started:.1f}s",
        extra={"flush": True},
    )


if __name__ == "__main__":
    main()
