from pathlib import Path

import pandas as pd

from src.monitoring.drift import run_prediction_drift_detection
from src.monitoring.production import prediction_log_to_feature_table, run_production_drift_detection
from src.utils.config import FEATURE_COLUMNS


def _prediction_log(path: Path, rows: int = 12) -> None:
    records = []
    for index in range(rows):
        records.append(
            {
                "timestamp": f"2026-01-01T00:{index:02d}:00Z",
                "server_id": "srv-01",
                "cpu_usage": 80 + index,
                "memory_usage": 75 + index,
                "request_count": 300 + index * 10,
                "error_rate": 0.1 + index * 0.01,
                "avg_latency_ms": 900 + index * 20,
                "p95_latency_ms": 1300 + index * 30,
                "prediction": "anomaly",
                "anomaly_score": -0.5,
                "risk_level": "high",
                "model_version": "v1",
            }
        )
    pd.DataFrame(records).to_csv(path, index=False)


def _reference_features(path: Path, rows: int = 24) -> None:
    records = []
    for index in range(rows):
        cpu = 30 + index
        memory = 45 + index
        requests = 120 + index
        error = 0.01 + index * 0.001
        avg_latency = 180 + index
        p95_latency = 300 + index
        record = {
            "cpu_usage": cpu,
            "memory_usage": memory,
            "request_count": requests,
            "error_rate": error,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "cpu_usage_roll_mean_3": cpu,
            "memory_usage_roll_mean_3": memory,
            "request_count_roll_mean_3": requests,
            "error_rate_roll_mean_3": error,
            "avg_latency_ms_roll_mean_3": avg_latency,
            "p95_latency_ms_roll_mean_3": p95_latency,
            "latency_error_interaction": avg_latency * (1.0 + error),
            "traffic_error_pressure": requests * (1.0 + 10.0 * error),
        }
        records.append(record)
    pd.DataFrame(records, columns=FEATURE_COLUMNS).to_csv(path, index=False)


def _prediction_drift_log(rows: int = 20) -> pd.DataFrame:
    records = []
    for index in range(rows):
        current_window = index >= rows // 2
        records.append(
            {
                "timestamp": f"2026-01-01T00:{index:02d}:00Z",
                "prediction": "anomaly" if current_window else "normal",
                "anomaly_score": -0.6 if current_window else 0.2,
            }
        )
    return pd.DataFrame(records)


def test_prediction_log_to_feature_table_builds_expected_features(tmp_path: Path) -> None:
    log_path = tmp_path / "predictions.csv"
    output_path = tmp_path / "production_features.csv"
    _prediction_log(log_path)

    result_path = prediction_log_to_feature_table(log_path, output_path)
    df = pd.read_csv(result_path)

    assert result_path == output_path
    assert set(FEATURE_COLUMNS).issubset(df.columns)
    assert len(df) == 12


def test_run_production_drift_detection_reports_completed_status(tmp_path: Path) -> None:
    log_path = tmp_path / "predictions.csv"
    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    report_path = tmp_path / "drift_report.json"
    _prediction_log(log_path)
    _reference_features(reference_path)

    result = run_production_drift_detection(
        log_path=log_path,
        reference_path=reference_path,
        current_features_path=current_path,
        report_path=report_path,
        threshold=0.0,
    )

    assert result["status"] == "completed"
    assert report_path.exists()
    assert current_path.exists()
    assert result["max_drift_score"] > 0
    assert result["data_drift_detected"] is True
    assert result["prediction_drift"]["status"] == "completed"
    assert result["prediction_drift_detected"] is False


def test_run_prediction_drift_detection_flags_shifted_prediction_distribution() -> None:
    result = run_prediction_drift_detection(_prediction_drift_log(), threshold=0.2)

    assert result["status"] == "completed"
    assert result["drift_detected"] is True
    assert "prediction_distribution" in result["drifted_outputs"]
    assert result["baseline_prediction_distribution"] == {"normal": 1.0}
    assert result["current_prediction_distribution"] == {"anomaly": 1.0}
