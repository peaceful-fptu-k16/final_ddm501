from __future__ import annotations

import json

from src.data.extract import extract_server_metrics
from src.data.preprocess import preprocess_data
from src.data.validate import validate_raw_data_as_dict
from src.features.build_features import create_features
from src.models.register import register_model_if_better
from src.models.train import train_anomaly_model
from src.monitoring.drift import run_drift_detection
from src.utils.config import ensure_directories, settings


def run_training_pipeline() -> dict[str, object]:
    ensure_directories()
    raw_path = extract_server_metrics()
    validation = validate_raw_data_as_dict(raw_path, fail_on_error=True)
    processed_path = preprocess_data(raw_path)
    feature_path = create_features(processed_path)
    training = train_anomaly_model(feature_path)
    registration = register_model_if_better(settings.model_dir)
    drift = run_drift_detection(settings.model_dir / "training_reference.csv", feature_path)
    return {
        "raw_path": str(raw_path),
        "validation": validation,
        "processed_path": str(processed_path),
        "feature_path": str(feature_path),
        "training": training,
        "registration": registration,
        "drift": drift,
    }


if __name__ == "__main__":
    print(json.dumps(run_training_pipeline(), indent=2))
