from __future__ import annotations

import csv
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.utils.config import BASE_FEATURES, ensure_directories, settings

PREDICTION_COLUMNS = [
    "timestamp",
    "server_id",
    *BASE_FEATURES,
    "prediction",
    "anomaly_score",
    "risk_level",
    "model_version",
]


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    server_id TEXT NOT NULL,
    cpu_usage DOUBLE PRECISION NOT NULL,
    memory_usage DOUBLE PRECISION NOT NULL,
    request_count DOUBLE PRECISION NOT NULL,
    error_rate DOUBLE PRECISION NOT NULL,
    avg_latency_ms DOUBLE PRECISION NOT NULL,
    p95_latency_ms DOUBLE PRECISION NOT NULL,
    prediction TEXT NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prediction_logs_timestamp
    ON prediction_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_logs_prediction
    ON prediction_logs (prediction);
"""


INSERT_SQL = """
INSERT INTO prediction_logs (
    timestamp,
    server_id,
    cpu_usage,
    memory_usage,
    request_count,
    error_rate,
    avg_latency_ms,
    p95_latency_ms,
    prediction,
    anomaly_score,
    risk_level,
    model_version
) VALUES (
    %(timestamp)s,
    %(server_id)s,
    %(cpu_usage)s,
    %(memory_usage)s,
    %(request_count)s,
    %(error_rate)s,
    %(avg_latency_ms)s,
    %(p95_latency_ms)s,
    %(prediction)s,
    %(anomaly_score)s,
    %(risk_level)s,
    %(model_version)s
);
"""


def _connect(database_url: str):
    import psycopg2

    return psycopg2.connect(database_url)


def _normalize_row(
    payload: dict[str, object],
    result: dict[str, object],
    timestamp: datetime | None = None,
) -> dict[str, object]:
    event_time = timestamp or datetime.now(UTC)
    return {
        "timestamp": event_time.isoformat(),
        "server_id": str(payload["server_id"]),
        "cpu_usage": float(payload["cpu_usage"]),
        "memory_usage": float(payload["memory_usage"]),
        "request_count": float(payload["request_count"]),
        "error_rate": float(payload["error_rate"]),
        "avg_latency_ms": float(payload["avg_latency_ms"]),
        "p95_latency_ms": float(payload["p95_latency_ms"]),
        "prediction": str(result["prediction"]),
        "anomaly_score": float(result["anomaly_score"]),
        "risk_level": str(result["risk_level"]),
        "model_version": str(result["model_version"]),
    }


def _append_csv(row: dict[str, object], path: Path | None = None) -> str:
    ensure_directories()
    target = Path(path or settings.production_log_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    exists = target.exists()
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREDICTION_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row[column] for column in PREDICTION_COLUMNS})
    return "csv"


def _append_postgres(row: dict[str, object], database_url: str) -> str:
    with closing(_connect(database_url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
                cursor.execute(INSERT_SQL, row)
    return "postgres"


def append_prediction_log(
    payload: dict[str, object],
    result: dict[str, object],
    timestamp: datetime | None = None,
    database_url: str | None = None,
    fallback_path: str | Path | None = None,
) -> str:
    row = _normalize_row(payload, result, timestamp)
    target_database = database_url if database_url is not None else settings.prediction_database_url
    if target_database:
        try:
            return _append_postgres(row, target_database)
        except Exception:
            return _append_csv(row, Path(fallback_path) if fallback_path else None)
    return _append_csv(row, Path(fallback_path) if fallback_path else None)


def load_prediction_logs(
    limit: int | None = None,
    database_url: str | None = None,
    fallback_path: str | Path | None = None,
) -> pd.DataFrame:
    target_database = database_url if database_url is not None else settings.prediction_database_url
    if target_database:
        try:
            query = """
            SELECT
                timestamp,
                server_id,
                cpu_usage,
                memory_usage,
                request_count,
                error_rate,
                avg_latency_ms,
                p95_latency_ms,
                prediction,
                anomaly_score,
                risk_level,
                model_version
            FROM prediction_logs
            ORDER BY timestamp DESC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            with closing(_connect(target_database)) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(CREATE_TABLE_SQL)
                connection.commit()
                df = pd.read_sql_query(query, connection)
            if not df.empty:
                return df.sort_values("timestamp")
        except Exception:
            pass

    source = Path(fallback_path or settings.production_log_path)
    if not source.exists():
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    df = pd.read_csv(source)
    if limit:
        df = df.tail(limit)
    return df
