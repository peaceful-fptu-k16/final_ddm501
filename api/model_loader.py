from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.utils.config import BASE_FEATURES, FEATURE_COLUMNS, settings


class ModelBundle:
    def __init__(self, model_dir: str | Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else self._resolve_model_dir()
        self.mlflow_model_uri = None if model_dir else settings.mlflow_model_uri
        self.model = None
        self.scaler = None
        self.feature_columns = FEATURE_COLUMNS
        self.version = "heuristic"
        self.source = "heuristic"
        self.load()

    @staticmethod
    def _resolve_model_dir() -> Path:
        registry_state = settings.registry_dir / "registry_state.json"
        if registry_state.exists():
            try:
                state = json.loads(registry_state.read_text(encoding="utf-8"))
                production_version = state.get("production_version")
                if production_version:
                    production_dir = settings.registry_dir / production_version
                    if (production_dir / "model.joblib").exists():
                        return production_dir
            except json.JSONDecodeError:
                pass
        return settings.model_dir

    @property
    def loaded(self) -> bool:
        if self.source == "mlflow":
            return self.model is not None
        return self.model is not None and self.scaler is not None

    def load(self) -> None:
        if self.mlflow_model_uri and self._load_mlflow_model():
            return

        model_path = self.model_dir / "model.joblib"
        scaler_path = self.model_dir / "scaler.joblib"
        features_path = self.model_dir / "feature_columns.json"
        version_path = self.model_dir / "version.txt"

        if model_path.exists() and scaler_path.exists():
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            self.source = "local_registry"
            if features_path.exists():
                self.feature_columns = json.loads(features_path.read_text(encoding="utf-8"))
            if version_path.exists():
                self.version = version_path.read_text(encoding="utf-8").strip() or "local"

    def _load_mlflow_model(self) -> bool:
        try:
            import mlflow
            import mlflow.sklearn
        except ImportError:
            return False

        try:
            if settings.mlflow_tracking_uri:
                mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            self.model = mlflow.sklearn.load_model(self.mlflow_model_uri)
            self.source = "mlflow"
            self.version = self.mlflow_model_uri or "mlflow"
            self.feature_columns = FEATURE_COLUMNS
            return True
        except Exception:
            self.model = None
            self.source = "heuristic"
            return False

    def _vectorize(self, payload: dict[str, Any]) -> np.ndarray:
        values: dict[str, float] = {feature: float(payload.get(feature, 0.0)) for feature in BASE_FEATURES}
        values.update(
            {
                "cpu_usage_roll_mean_3": values["cpu_usage"],
                "memory_usage_roll_mean_3": values["memory_usage"],
                "request_count_roll_mean_3": values["request_count"],
                "error_rate_roll_mean_3": values["error_rate"],
                "avg_latency_ms_roll_mean_3": values["avg_latency_ms"],
                "p95_latency_ms_roll_mean_3": values["p95_latency_ms"],
                "latency_error_interaction": values["avg_latency_ms"] * (1.0 + values["error_rate"]),
                "traffic_error_pressure": values["request_count"] * (1.0 + 10.0 * values["error_rate"]),
            }
        )
        return np.asarray([[values.get(feature, 0.0) for feature in self.feature_columns]], dtype=float)

    def _heuristic_predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        pressure = 0.0
        pressure += max(float(payload["cpu_usage"]) - 80.0, 0.0) / 20.0
        pressure += max(float(payload["memory_usage"]) - 85.0, 0.0) / 15.0
        pressure += min(float(payload["error_rate"]) / 0.25, 2.0)
        pressure += max(float(payload["avg_latency_ms"]) - 700.0, 0.0) / 900.0
        pressure += max(float(payload["p95_latency_ms"]) - 1200.0, 0.0) / 1200.0
        score = round(-min(pressure / 5.0, 1.0), 6)
        prediction = "anomaly" if score <= -0.35 else "normal"
        return {
            "prediction": prediction,
            "anomaly_score": score,
            "risk_level": self._risk_level(score, prediction),
            "model_version": self.version,
        }

    @staticmethod
    def _risk_level(score: float, prediction: str) -> str:
        if prediction == "normal":
            return "low"
        if score <= -0.55:
            return "high"
        return "medium"

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.loaded:
            return self._heuristic_predict(payload)

        vector = self._vectorize(payload)
        frame = pd.DataFrame(vector, columns=self.feature_columns)
        if self.source == "mlflow":
            prediction_value = int(self.model.predict(frame)[0])
            score = float(self.model.decision_function(frame)[0]) if hasattr(self.model, "decision_function") else 0.0
            prediction = "anomaly" if prediction_value == -1 else "normal"
            return {
                "prediction": prediction,
                "anomaly_score": round(score, 6),
                "risk_level": self._risk_level(score, prediction),
                "model_version": self.version,
            }

        scaled = self.scaler.transform(frame)
        prediction_value = int(self.model.predict(scaled)[0])
        score = float(self.model.decision_function(scaled)[0])
        prediction = "anomaly" if prediction_value == -1 else "normal"
        return {
            "prediction": prediction,
            "anomaly_score": round(score, 6),
            "risk_level": self._risk_level(score, prediction),
            "model_version": self.version,
        }
