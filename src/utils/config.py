from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_FEATURES = [
    "cpu_usage",
    "memory_usage",
    "request_count",
    "error_rate",
    "avg_latency_ms",
    "p95_latency_ms",
]

ROLLING_FEATURES = [
    "cpu_usage_roll_mean_3",
    "memory_usage_roll_mean_3",
    "request_count_roll_mean_3",
    "error_rate_roll_mean_3",
    "avg_latency_ms_roll_mean_3",
    "p95_latency_ms_roll_mean_3",
    "latency_error_interaction",
    "traffic_error_pressure",
]

FEATURE_COLUMNS = BASE_FEATURES + ROLLING_FEATURES

REQUIRED_RAW_COLUMNS = [
    "timestamp",
    "server_id",
    *BASE_FEATURES,
]

NUMERIC_RANGES = {
    "cpu_usage": (0.0, 100.0),
    "memory_usage": (0.0, 100.0),
    "request_count": (0.0, None),
    "error_rate": (0.0, 1.0),
    "avg_latency_ms": (0.0, None),
    "p95_latency_ms": (0.0, None),
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    raw_data_path: Path
    processed_data_path: Path
    feature_data_path: Path
    production_log_path: Path
    model_dir: Path
    registry_dir: Path
    report_dir: Path
    prediction_database_url: str | None
    mlflow_tracking_uri: str | None
    mlflow_experiment: str
    mlflow_model_uri: str | None
    mlflow_registered_model_name: str | None
    mlflow_registry_alias: str
    drift_threshold: float

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
        report_dir = Path(os.getenv("REPORT_DIR", PROJECT_ROOT / "reports"))
        model_dir = Path(os.getenv("MODEL_DIR", PROJECT_ROOT / "models" / "latest"))
        registry_dir = Path(os.getenv("REGISTRY_DIR", PROJECT_ROOT / "models" / "registry"))
        return cls(
            data_dir=data_dir,
            raw_data_path=Path(os.getenv("RAW_DATA_PATH", data_dir / "raw" / "server_metrics.csv")),
            processed_data_path=Path(
                os.getenv("PROCESSED_DATA_PATH", data_dir / "processed" / "server_metrics_clean.csv")
            ),
            feature_data_path=Path(os.getenv("FEATURE_DATA_PATH", data_dir / "processed" / "features.csv")),
            production_log_path=Path(
                os.getenv("PRODUCTION_LOG_PATH", data_dir / "production" / "predictions.csv")
            ),
            model_dir=model_dir,
            registry_dir=registry_dir,
            report_dir=report_dir,
            prediction_database_url=os.getenv("PREDICTION_DATABASE_URL"),
            mlflow_tracking_uri=os.getenv(
                "MLFLOW_TRACKING_URI",
                f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}",
            ),
            mlflow_experiment=os.getenv("MLFLOW_EXPERIMENT", "server-log-anomaly"),
            mlflow_model_uri=os.getenv("MLFLOW_MODEL_URI"),
            mlflow_registered_model_name=os.getenv("MLFLOW_REGISTERED_MODEL_NAME"),
            mlflow_registry_alias=os.getenv("MLFLOW_REGISTRY_ALIAS", "production"),
            drift_threshold=float(os.getenv("DRIFT_THRESHOLD", "0.2")),
        )


settings = Settings.from_env()


def ensure_directories() -> None:
    for path in [
        settings.raw_data_path.parent,
        settings.processed_data_path.parent,
        settings.feature_data_path.parent,
        settings.production_log_path.parent,
        settings.model_dir,
        settings.registry_dir,
        settings.report_dir / "data_quality",
        settings.report_dir / "model_evaluation",
        settings.report_dir / "drift",
    ]:
        path.mkdir(parents=True, exist_ok=True)
