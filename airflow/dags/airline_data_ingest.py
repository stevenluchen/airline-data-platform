from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
import pendulum

from ingest_state_vectors import fetch_states, insert_states
from transform_state_vectors import transform_snapshot
from db import get_engine

# Default arguments for the DAG
default_args = {
    'owner': 'data-platform',
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

# DAG definition
dag = DAG(
    'airline_data_ingest',
    default_args=default_args,
    description='Ingest and transform OpenSky state vector data',
    schedule='*/10 * * * *',  # Every 10 minutes
    start_date=pendulum.datetime(2026, 9, 12, tz="UTC"),  # Start date in UTC
    catchup=False,
    tags=['airline-data', 'opensky', 'ingestion'],
)

def fetch_and_ingest(**context):
    try:
        engine = get_engine()
        data = fetch_states()
        result = insert_states(data, engine)
        
        return result
    except Exception as e:
        raise AirflowException(f"Failed to fetch and ingest state vectors: {str(e)}")

def transform_snapshot_task(**context):
    try:
        result = context['ti'].xcom_pull(task_ids='fetch_and_ingest')
        snapshot_id = result['snapshot_id']
        aircraft_count = result['aircraft_count']

        engine = get_engine()
        rows_transformed = transform_snapshot(engine, snapshot_id)
        
        return {
            'snapshot_id': snapshot_id,
            'aircraft_count': aircraft_count,
            'rows_transformed': rows_transformed
        }
    except Exception as e:
        raise AirflowException(f"Failed to transform snapshot: {str(e)}")

with dag:
    ingest_task = PythonOperator(
        task_id='fetch_and_ingest',
        python_callable=fetch_and_ingest
    )

    transform_task = PythonOperator(
        task_id='transform_snapshot',
        python_callable=transform_snapshot_task
    )

    ingest_task >> transform_task
