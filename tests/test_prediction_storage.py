from pathlib import Path

from src.storage.prediction_logs import append_prediction_log, load_prediction_logs


def _payload() -> dict[str, object]:
    return {
        "server_id": "srv-01",
        "cpu_usage": 92.5,
        "memory_usage": 88.1,
        "request_count": 420,
        "error_rate": 0.27,
        "avg_latency_ms": 1600,
        "p95_latency_ms": 2400,
    }


def _result() -> dict[str, object]:
    return {
        "prediction": "anomaly",
        "anomaly_score": -0.61,
        "risk_level": "high",
        "model_version": "v1",
    }


def test_append_prediction_log_falls_back_to_csv(tmp_path: Path) -> None:
    log_path = tmp_path / "predictions.csv"

    backend = append_prediction_log(
        _payload(),
        _result(),
        request_id="req-123",
        database_url="",
        fallback_path=log_path,
    )
    df = load_prediction_logs(database_url="", fallback_path=log_path)

    assert backend == "csv"
    assert len(df) == 1
    assert df.iloc[0]["prediction"] == "anomaly"
    assert df.iloc[0]["request_id"] == "req-123"
