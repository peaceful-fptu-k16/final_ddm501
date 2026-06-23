from pathlib import Path

import pandas as pd
import pytest

from src.data.validate import validate_raw_data


def test_validate_raw_data_accepts_valid_schema(tmp_path: Path) -> None:
    path = tmp_path / "valid.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "server_id": "srv-01",
                "cpu_usage": 50.0,
                "memory_usage": 60.0,
                "request_count": 120,
                "error_rate": 0.01,
                "avg_latency_ms": 200,
                "p95_latency_ms": 350,
            }
        ]
    ).to_csv(path, index=False)

    result = validate_raw_data(path, tmp_path / "report.json")

    assert result.valid is True
    assert result.row_count == 1


def test_validate_raw_data_rejects_out_of_range_values(tmp_path: Path) -> None:
    path = tmp_path / "invalid.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "server_id": "srv-01",
                "cpu_usage": 150.0,
                "memory_usage": 60.0,
                "request_count": 120,
                "error_rate": 0.01,
                "avg_latency_ms": 200,
                "p95_latency_ms": 350,
            }
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError):
        validate_raw_data(path, tmp_path / "report.json")


def test_validate_raw_data_rejects_invalid_latency_order(tmp_path: Path) -> None:
    path = tmp_path / "invalid_latency.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "server_id": "srv-01",
                "cpu_usage": 50.0,
                "memory_usage": 60.0,
                "request_count": 120,
                "error_rate": 0.01,
                "avg_latency_ms": 500,
                "p95_latency_ms": 300,
            }
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError):
        validate_raw_data(path, tmp_path / "report.json")
