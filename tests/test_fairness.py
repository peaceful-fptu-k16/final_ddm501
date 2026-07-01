import pandas as pd

from src.monitoring.fairness import run_fairness_report


def test_run_fairness_report_computes_group_gap(tmp_path) -> None:
    log_path = tmp_path / "predictions.csv"
    report_path = tmp_path / "fairness.json"
    pd.DataFrame(
        [
            {"server_id": "srv-a", "prediction": "anomaly", "risk_level": "high", "anomaly_score": -0.7},
            {"server_id": "srv-a", "prediction": "normal", "risk_level": "low", "anomaly_score": 0.1},
            {"server_id": "srv-b", "prediction": "normal", "risk_level": "low", "anomaly_score": 0.2},
            {"server_id": "srv-b", "prediction": "normal", "risk_level": "low", "anomaly_score": 0.3},
        ]
    ).to_csv(log_path, index=False)

    report = run_fairness_report(log_path=log_path, report_path=report_path, group_column="server_id")

    assert report["status"] == "completed"
    assert report["max_anomaly_rate_gap"] == 0.5
    assert report["fairness_alert"] is True
    assert report_path.exists()
