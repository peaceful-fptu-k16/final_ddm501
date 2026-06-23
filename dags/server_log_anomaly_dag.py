from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.extract import extract_server_metrics
from src.data.preprocess import preprocess_data
from src.data.validate import validate_raw_data_as_dict
from src.features.build_features import create_features
from src.models.register import register_model_if_better
from src.models.train import train_anomaly_model
from src.monitoring.drift import run_drift_detection
from src.utils.config import settings


def notify_ops(**context: object) -> None:
    drift = context["ti"].xcom_pull(task_ids="run_drift_detection")
    if isinstance(drift, str):
        drift = json.loads(drift)
    if drift and drift.get("drift_detected"):
        print(f"OPS ALERT: Drift detected: {drift['drifted_features']}")
    else:
        print("OPS INFO: Pipeline completed without drift alert")


with DAG(
    dag_id="server_log_anomaly_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["mlops", "ops", "anomaly-detection"],
) as dag:
    extract_data = PythonOperator(
        task_id="extract_server_metrics",
        python_callable=extract_server_metrics,
        do_xcom_push=False,
    )

    validate_data = PythonOperator(
        task_id="validate_raw_data",
        python_callable=validate_raw_data_as_dict,
    )

    preprocess = PythonOperator(
        task_id="preprocess_data",
        python_callable=preprocess_data,
        do_xcom_push=False,
    )

    feature_engineering = PythonOperator(
        task_id="create_features",
        python_callable=create_features,
        do_xcom_push=False,
    )

    train_model = PythonOperator(
        task_id="train_anomaly_model",
        python_callable=train_anomaly_model,
    )

    register = PythonOperator(
        task_id="register_model_if_better",
        python_callable=register_model_if_better,
        op_kwargs={"model_dir": settings.model_dir},
    )

    drift_check = PythonOperator(
        task_id="run_drift_detection",
        python_callable=run_drift_detection,
        op_kwargs={
            "reference_path": settings.model_dir / "training_reference.csv",
            "current_path": settings.feature_data_path,
        },
    )

    notify = PythonOperator(
        task_id="notify_ops",
        python_callable=notify_ops,
    )

    extract_data >> validate_data >> preprocess >> feature_engineering
    feature_engineering >> train_model >> register >> drift_check >> notify
