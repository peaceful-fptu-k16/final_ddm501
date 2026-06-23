from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retraining import trigger_retraining_if_needed


with DAG(
    dag_id="server_log_anomaly_retraining",
    start_date=datetime(2026, 1, 1),
    schedule="0 */6 * * *",
    catchup=False,
    tags=["mlops", "drift", "retraining"],
) as dag:
    check_drift_and_retrain = PythonOperator(
        task_id="check_production_drift_and_retrain",
        python_callable=trigger_retraining_if_needed,
    )
