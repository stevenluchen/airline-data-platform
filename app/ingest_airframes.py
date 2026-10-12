#print("[airframes] module import started", flush=True)
import pandas as pd
#print("[airframes] pandas imported", flush=True)
from db import get_engine
#print("[airframes] db imported", flush=True)
from tqdm import tqdm
#print("[airframes] tqdm imported", flush=True)
from sqlalchemy import text
#print("[airframes] sqlalchemy imported", flush=True)
import requests
#print("[airframes] requests imported", flush=True)
from pathlib import Path
#print("[airframes] pathlib imported", flush=True)
import time
#print("[airframes] all modules imported", flush=True)

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
    print(f"[airframes] Starting GitHub release discovery: {RELEASES_URL}", flush=True)
    print("[airframes] Sending GitHub API request...", flush=True)
    response = requests.get(
        RELEASES_URL,
        params={"per_page": 10},
        timeout=30,
    )
    print(
        "[airframes] GitHub response received: "
        f"status={response.status_code}, "
        f"bytes={len(response.content):,}, "
        f"elapsed={time.monotonic() - started:.2f}s",
        flush=True,
    )
    response.raise_for_status()

    releases = response.json()
    print(f"[airframes] Releases returned: {len(releases)}", flush=True)

    for release_number, release in enumerate(releases, start=1):
        print(
            f"[airframes] Inspecting release {release_number}: "
            f"tag={release.get('tag_name')!r}, "
            f"published={release.get('published_at')!r}, "
            f"draft={release.get('draft')}, "
            f"prerelease={release.get('prerelease')}, "
            f"assets={len(release.get('assets', []))}",
            flush=True,
        )
        for asset in release["assets"]:
            name = asset["name"]
            print(f"[airframes]   Checking asset: {name}", flush=True)
            if name.startswith("openairframes_adsb_") and name.endswith(".csv.gz"):
                url = asset["browser_download_url"]
                print(
                    f"[airframes] Selected asset: {url} "
                    f"(total elapsed={time.monotonic() - started:.2f}s)",
                    flush=True,
                )
                return url

    print(
        f"[airframes] No matching asset found "
        f"(total elapsed={time.monotonic() - started:.2f}s)",
        flush=True,
    )
    raise RuntimeError("No OpenAirframes CSV release asset found")

def load_and_validate_staging(url: str) -> dict:
    started = time.monotonic()
    print(f"[airframes] Starting staging load from {url}", flush=True)

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
    print("[airframes] CSV reader initialized; beginning chunk processing", flush=True)

    engine = get_engine()

    latest_chunks = []
    chunk_count = 0
    source_rows = 0
    valid_rows = 0
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
        chunk = (
            chunk.sort_values("time_parsed", ascending=False)
            .drop_duplicates("icao24", keep="first")
            .drop(columns="time_parsed")
        )
        valid_rows += len(chunk)
        latest_chunks.append(chunk)
        if chunk_count % 100 == 0:
            print(
                f"[airframes] Processed {chunk_count:,} chunks, "
                f"source_rows={source_rows:,}, "
                f"chunk_candidates={valid_rows:,}, "
                f"elapsed={time.monotonic() - read_started:.1f}s",
                flush=True,
            )

    print(
        f"[airframes] Finished source processing: chunks={chunk_count:,}, "
        f"source_rows={source_rows:,}, candidates={valid_rows:,}, "
        f"elapsed={time.monotonic() - read_started:.1f}s",
        flush=True,
    )

    latest = (
        pd.concat(latest_chunks, ignore_index=True)
        # OpenAirframes timestamps are ISO-formatted, so lexical ordering is
        # chronological and avoids an expensive per-row dateutil parse.
        .assign(time_parsed=lambda df: df["time"])
        .sort_values("time_parsed", ascending=False)
        .drop_duplicates("icao24", keep="first")
        .drop(columns="time_parsed")
    )
    print(
        f"[airframes] Final deduplication complete: "
        f"latest_rows={len(latest):,}, "
        f"elapsed={time.monotonic() - started:.1f}s",
        flush=True,
    )

    ddl_started = time.monotonic()
    print(f"[airframes] Creating staging table from {staging_ddl_path()}", flush=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(staging_ddl_path().read_text())
    print(
        f"[airframes] Staging table created in {time.monotonic() - ddl_started:.1f}s",
        flush=True,
    )

    insert_started = time.monotonic()
    print(f"[airframes] Inserting {len(latest):,} rows into staging", flush=True)
    latest.to_sql(
        STAGING_TABLE,
        engine,
        schema="staging",
        if_exists="append",
        index=False,
        method="multi",
    )
    print(
        f"[airframes] Staging insert complete in "
        f"{time.monotonic() - insert_started:.1f}s",
        flush=True,
    )

    validation_started = time.monotonic()
    print("[airframes] Validating staging row counts", flush=True)
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

    print(
        f"[airframes] Staging validated: rows={row_count:,}, "
        f"distinct_icao24={distinct_aircraft:,}, "
        f"elapsed={time.monotonic() - validation_started:.1f}s, "
        f"total={time.monotonic() - started:.1f}s",
        flush=True,
    )

    return {
        "row_count": row_count,
        "distinct_aircraft": distinct_aircraft,
        "validated": True,
    }

def promote_staging_table():
    started = time.monotonic()
    engine = get_engine()
    print("[airframes] Promoting staging table to raw.airframes_history", flush=True)

    # Swap only after the complete snapshot has loaded successfully.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS raw.airframes_history;"))
        conn.execute(text(f"ALTER TABLE staging.{STAGING_TABLE} RENAME TO airframes_history;"))
        conn.execute(text("ALTER TABLE staging.airframes_history SET SCHEMA raw;"))

    print(
        f"[airframes] Promotion complete in {time.monotonic() - started:.1f}s",
        flush=True,
    )


def rebuild_dim_aircraft():
    """Rebuild the aircraft dimension from the current raw snapshot."""
    started = time.monotonic()
    engine = get_engine()
    sql_path = dim_aircraft_sql_path()
    print(f"[airframes] Rebuilding analytics.dim_aircraft from {sql_path}", flush=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(sql_path.read_text())

    print(
        f"[airframes] Aircraft dimension rebuild complete in "
        f"{time.monotonic() - started:.1f}s",
        flush=True,
    )


def main():
    started = time.monotonic()
    print("[airframes] Airframes refresh started", flush=True)
    print("Discovering latest OpenAirframes release...")
    url = get_latest_airframes_url()
    print(f"Selected OpenAirframes asset: {url}")

    result = load_and_validate_staging(url)
    promote_staging_table()
    rebuild_dim_aircraft()
    print(
        "[airframes] Airframes refresh complete: "
        f"{result['row_count']:,} aircraft records, "
        f"total elapsed={time.monotonic() - started:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
