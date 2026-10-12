FROM apache/airflow:3.3.1

COPY app/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /opt/airflow/app/
COPY sql/ /opt/airflow/sql/

ENV PYTHONPATH=/opt/airflow/app
