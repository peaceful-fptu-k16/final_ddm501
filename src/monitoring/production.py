from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.monitoring.drift import run_drift_detection, run_prediction_drift_detection
from src.storage.prediction_logs import load_prediction_logs
from src.utils.config import BASE_FEATURES, FEATURE_COLUMNS, ensure_directories, settings


def _load_prediction_log(input_path: str | Path | None = None) -> pd.DataFrame:
    if input_path:
        source = Path(input_path)
        if not source.exists():
            raise FileNotFoundError(f"Prediction log does not exist: {source}")
        return pd.read_csv(source)

    df = load_prediction_logs()
    if df.empty:
        raise FileNotFoundError("Prediction log does not contain any rows")
    return df


def prediction_log_frame_to_feature_table(
    prediction_log: pd.DataFrame,
    output_path: str | Path | None = None,
) -> Path:
    ensure_directories()
    output = Path(output_path or settings.data_dir / "production" / "production_features.csv")
    df = prediction_log.copy()

    missing = [column for column in ["timestamp", "server_id", *BASE_FEATURES] if column not in df.columns]
    if missing:
        raise ValueError(f"Prediction log is missing required columns: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "server_id"]).sort_values(["server_id", "timestamp"])

    for column in BASE_FEATURES:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
        df[f"{column}_roll_mean_3"] = (
            df.groupby("server_id", group_keys=False)[column]
            .transform(lambda values: values.rolling(window=3, min_periods=1).mean())
            .fillna(df[column])
        )

    df["latency_error_interaction"] = df["avg_latency_ms"] * (1.0 + df["error_rate"])
    df["traffic_error_pressure"] = df["request_count"] * (1.0 + 10.0 * df["error_rate"])

    output.parent.mkdir(parents=True, exist_ok=True)
    df[["timestamp", "server_id", *FEATURE_COLUMNS]].to_csv(output, index=False)
    return output


def prediction_log_to_feature_table(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    return prediction_log_frame_to_feature_table(_load_prediction_log(input_path), output_path)


def _write_report(report: Path, payload: dict[str, Any]) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _skipped_data_drift_payload(reason: str, reference: Path | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "drift_detected": False,
        "status": "skipped",
        "reason": reason,
        "max_drift_score": 0.0,
        "drifted_features": [],
        "feature_scores": {},
    }
    if reference is not None:
        payload["reference_path"] = str(reference)
    return payload


def _combine_drift_payloads(
    data_drift: dict[str, Any],
    prediction_drift: dict[str, Any],
    prediction_log_path: str,
) -> dict[str, Any]:
    data_drift_detected = bool(data_drift.get("drift_detected"))
    prediction_drift_detected = bool(prediction_drift.get("drift_detected"))
    max_data_score = float(data_drift.get("max_drift_score", 0.0))
    max_prediction_score = float(prediction_drift.get("max_drift_score", 0.0))
    status = "completed" if "completed" in {data_drift.get("status"), prediction_drift.get("status")} else "skipped"

    payload = dict(data_drift)
    payload.update(
        {
            "status": status,
            "drift_detected": data_drift_detected or prediction_drift_detected,
            "data_drift_detected": data_drift_detected,
            "prediction_drift_detected": prediction_drift_detected,
            "max_drift_score": round(max(max_data_score, max_prediction_score), 6),
            "max_data_drift_score": round(max_data_score, 6),
            "max_prediction_drift_score": round(max_prediction_score, 6),
            "drifted_outputs": prediction_drift.get("drifted_outputs", []),
            "data_drift": data_drift,
            "prediction_drift": prediction_drift,
            "prediction_log_path": prediction_log_path,
        }
    )
    return payload


def run_production_drift_detection(
    log_path: str | Path | None = None,
    reference_path: str | Path | None = None,
    current_features_path: str | Path | None = None,
    report_path: str | Path | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    ensure_directories()
    report = Path(report_path or settings.report_dir / "drift" / "latest_production_report.json")
    reference = Path(reference_path or settings.model_dir / "training_reference.csv")

    if log_path and not Path(log_path).exists():
        payload = {
            "drift_detected": False,
            "status": "skipped",
            "reason": f"Prediction log does not exist: {Path(log_path)}",
            "max_drift_score": 0.0,
            "drifted_features": [],
        }
        _write_report(report, payload)
        return payload

    try:
        prediction_log = _load_prediction_log(log_path)
    except FileNotFoundError as exc:
        payload = {
            "drift_detected": False,
            "status": "skipped",
            "reason": str(exc),
            "max_drift_score": 0.0,
            "drifted_features": [],
            "prediction_log_path": str(Path(log_path) if log_path else settings.production_log_path),
        }
        _write_report(report, payload)
        return payload

    prediction_drift = run_prediction_drift_detection(prediction_log, threshold=threshold)
    prediction_log_path = str(Path(log_path) if log_path else settings.production_log_path)

    if not reference.exists():
        data_drift = _skipped_data_drift_payload(f"Reference data does not exist: {reference}", reference)
        payload = _combine_drift_payloads(data_drift, prediction_drift, prediction_log_path)
        _write_report(report, payload)
        return payload

    try:
        current_features = prediction_log_frame_to_feature_table(prediction_log, current_features_path)
    except FileNotFoundError as exc:
        data_drift = _skipped_data_drift_payload(str(exc), reference)
        payload = _combine_drift_payloads(data_drift, prediction_drift, prediction_log_path)
        _write_report(report, payload)
        return payload

    data_drift = run_drift_detection(
        reference_path=reference,
        current_path=current_features,
        report_path=report,
        threshold=threshold,
    )
    data_drift["status"] = "completed"
    payload = _combine_drift_payloads(data_drift, prediction_drift, prediction_log_path)
    _write_report(report, payload)
    return payload
