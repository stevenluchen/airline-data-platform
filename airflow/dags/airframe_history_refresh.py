from datetime import timedelta
import pendulum

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.providers.standard.operators.python import PythonOperator


def discover_release():
    print("[airframes DAG] task callable entered", flush=True)
    try:
        print("[airframes DAG] importing ingest_airframes", flush=True)
        from ingest_airframes import get_latest_airframes_url
        print("[airframes DAG] import completed", flush=True)

        print("[airframes DAG] discover_release task started", flush=True)
        url = get_latest_airframes_url()
        print(f"[airframes DAG] discover_release task completed: {url}", flush=True)
        return url
    except Exception as e:
        raise AirflowException(f"Release discovery failed: {e}") from e


def stage_and_validate(**context):
    try:
        from ingest_airframes import load_and_validate_staging

        url = context["ti"].xcom_pull(task_ids="discover_release")
        if not url:
            raise ValueError("No release URL returned")

        result = load_and_validate_staging(url)

        return result

    except Exception as e:
        raise AirflowException(f"Staging/validation failed: {e}") from e


def promote_snapshot(**context):
    try:
        from ingest_airframes import promote_staging_table

        result = context["ti"].xcom_pull(task_ids="stage_and_validate")
        if not result or not result.get("validated"):
            raise ValueError("Staging snapshot was not validated")

        promote_staging_table()

    except Exception as e:
        raise AirflowException(f"Snapshot promotion failed: {e}") from e


def rebuild_aircraft_dimension():
    try:
        from ingest_airframes import rebuild_dim_aircraft

        rebuild_dim_aircraft()
    except Exception as e:
        raise AirflowException(f"Aircraft dimension rebuild failed: {e}") from e


with DAG(
    dag_id="airframe_history_refresh",
    description="Refresh OpenAirframes reference data from GitHub",
    schedule="0 8 * * *",  # Daily at 08:00 UTC
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    max_active_runs=1,
    tags=["airline-data", "reference-data"],
) as dag:

    discover = PythonOperator(
        task_id="discover_release",
        python_callable=discover_release,
    )

    stage = PythonOperator(
        task_id="stage_and_validate",
        python_callable=stage_and_validate,
    )

    promote = PythonOperator(
        task_id="promote_snapshot",
        python_callable=promote_snapshot,
    )

    rebuild = PythonOperator(
        task_id="rebuild_dim_aircraft",
        python_callable=rebuild_aircraft_dimension,
    )

    discover >> stage >> promote >> rebuild
