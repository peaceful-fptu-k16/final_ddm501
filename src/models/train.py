from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.models.evaluate import evaluate_predictions
from src.utils.config import FEATURE_COLUMNS, ensure_directories, settings


def _json_ready(metrics: dict[str, Any]) -> dict[str, Any]:
    ready: dict[str, Any] = {}
    for key, value in metrics.items():
        if hasattr(value, "item"):
            ready[key] = value.item()
        else:
            ready[key] = value
    return ready


def _log_to_mlflow(
    model: IsolationForest,
    scaler: StandardScaler,
    metrics: dict[str, Any],
    params: dict[str, Any],
    model_dir: Path,
    run_name: str,
) -> str | None:
    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        return "MLflow is not installed; skipped tracking"

    try:
        if settings.mlflow_tracking_uri:
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(params)
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(key, float(value))
            pipeline = Pipeline([("scaler", scaler), ("model", model)])
            model_info = mlflow.sklearn.log_model(
                pipeline,
                "model",
                registered_model_name=settings.mlflow_registered_model_name,
            )
            _set_registry_alias(model_info)
            mlflow.log_artifact(str(model_dir / "scaler.joblib"))
            mlflow.log_artifact(str(model_dir / "feature_columns.json"))
            mlflow.log_artifact(str(model_dir / "metrics.json"))
            return mlflow.active_run().info.run_id if mlflow.active_run() else None
    except Exception as exc:  # pragma: no cover - depends on external MLflow service
        return f"MLflow tracking failed: {exc}"


def _set_registry_alias(model_info: Any) -> None:
    if not settings.mlflow_registered_model_name:
        return
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        version = getattr(model_info, "registered_model_version", None)
        if not version:
            versions = client.search_model_versions(f"name = '{settings.mlflow_registered_model_name}'")
            if versions:
                version = max(versions, key=lambda item: int(item.version)).version
        if version:
            client.set_registered_model_alias(
                settings.mlflow_registered_model_name,
                settings.mlflow_registry_alias,
                str(version),
            )
    except Exception:
        return


def train_anomaly_model(
    input_path: str | Path | None = None,
    model_dir: str | Path | None = None,
    run_name: str = "isolation_forest_v1",
) -> dict[str, Any]:
    ensure_directories()
    source = Path(input_path or settings.feature_data_path)
    output_dir = Path(model_dir or settings.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(source)
    missing = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Feature data is missing columns: {missing}")

    x = df[FEATURE_COLUMNS].fillna(0.0)
    y = df["is_anomaly"].astype(int) if "is_anomaly" in df.columns else None
    contamination = 0.05
    if y is not None and y.mean() > 0:
        contamination = float(min(max(y.mean(), 0.01), 0.3))

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    model_params = {
        "n_estimators": 150,
        "contamination": round(contamination, 6),
        "random_state": 42,
    }
    tracking_params = {
        "model_type": "IsolationForest",
        **model_params,
    }
    model = IsolationForest(**model_params)
    predictions = model.fit_predict(x_scaled)

    if y is not None:
        metrics = evaluate_predictions(y, predictions)
    else:
        metrics = {"anomaly_rate": round(float((predictions == -1).mean()), 6)}

    metrics["training_rows"] = int(len(df))

    joblib.dump(model, output_dir / "model.joblib")
    joblib.dump(scaler, output_dir / "scaler.joblib")
    (output_dir / "feature_columns.json").write_text(json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(_json_ready(metrics), indent=2), encoding="utf-8")
    df[FEATURE_COLUMNS].to_csv(output_dir / "training_reference.csv", index=False)
    (output_dir / "version.txt").write_text("local", encoding="utf-8")

    mlflow_status = _log_to_mlflow(model, scaler, metrics, tracking_params, output_dir, run_name)
    if mlflow_status:
        metrics["mlflow_status"] = mlflow_status
        (output_dir / "metrics.json").write_text(json.dumps(_json_ready(metrics), indent=2), encoding="utf-8")

    return {
        "model_dir": str(output_dir),
        "metrics": _json_ready(metrics),
        "params": tracking_params,
    }


if __name__ == "__main__":
    print(json.dumps(train_anomaly_model(), indent=2))
