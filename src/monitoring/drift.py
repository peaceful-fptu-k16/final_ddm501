from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import FEATURE_COLUMNS, ensure_directories, settings


def population_stability_index(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy()
    cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy()
    if len(ref) == 0 or len(cur) == 0:
        return 0.0

    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)
    eps = 1e-6
    ref_pct = ref_counts / max(ref_counts.sum(), 1) + eps
    cur_pct = cur_counts / max(cur_counts.sum(), 1) + eps
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def categorical_population_stability_index(reference: pd.Series, current: pd.Series) -> float:
    ref = reference.dropna().astype(str)
    cur = current.dropna().astype(str)
    if ref.empty or cur.empty:
        return 0.0

    categories = sorted(set(ref.unique()) | set(cur.unique()))
    eps = 1e-6
    ref_pct = np.array([(ref == category).mean() + eps for category in categories])
    cur_pct = np.array([(cur == category).mean() + eps for category in categories])
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def categorical_distribution(values: pd.Series) -> dict[str, float]:
    series = values.dropna().astype(str)
    if series.empty:
        return {}
    counts = series.value_counts(normalize=True).sort_index()
    return {str(label): round(float(value), 6) for label, value in counts.items()}


def run_prediction_drift_detection(
    prediction_log: pd.DataFrame,
    threshold: float | None = None,
) -> dict[str, Any]:
    drift_threshold = settings.drift_threshold if threshold is None else threshold
    if prediction_log.empty:
        return {
            "status": "skipped",
            "reason": "Prediction log does not contain any rows",
            "drift_detected": False,
            "drift_threshold": drift_threshold,
            "max_drift_score": 0.0,
            "drifted_outputs": [],
            "output_scores": {},
        }
    if "prediction" not in prediction_log.columns:
        return {
            "status": "skipped",
            "reason": "Prediction log is missing required column: prediction",
            "drift_detected": False,
            "drift_threshold": drift_threshold,
            "max_drift_score": 0.0,
            "drifted_outputs": [],
            "output_scores": {},
        }

    df = prediction_log.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")

    midpoint = len(df) // 2
    if midpoint == 0 or len(df) - midpoint == 0:
        return {
            "status": "skipped",
            "reason": "Prediction log needs at least two rows to compare baseline and current windows",
            "drift_detected": False,
            "drift_threshold": drift_threshold,
            "max_drift_score": 0.0,
            "drifted_outputs": [],
            "output_scores": {},
        }

    baseline = df.iloc[:midpoint]
    current = df.iloc[midpoint:]
    output_scores = {
        "prediction_distribution": round(
            categorical_population_stability_index(baseline["prediction"], current["prediction"]),
            6,
        )
    }

    payload: dict[str, Any] = {
        "status": "completed",
        "drift_threshold": drift_threshold,
        "baseline_window_size": int(len(baseline)),
        "current_window_size": int(len(current)),
        "baseline_prediction_distribution": categorical_distribution(baseline["prediction"]),
        "current_prediction_distribution": categorical_distribution(current["prediction"]),
    }

    if "anomaly_score" in df.columns:
        baseline_scores = pd.to_numeric(baseline["anomaly_score"], errors="coerce").dropna()
        current_scores = pd.to_numeric(current["anomaly_score"], errors="coerce").dropna()
        if not baseline_scores.empty and not current_scores.empty:
            baseline_mean = float(baseline_scores.mean())
            current_mean = float(current_scores.mean())
            output_scores["anomaly_score_mean_delta"] = round(abs(current_mean - baseline_mean), 6)
            payload["baseline_anomaly_score_mean"] = round(baseline_mean, 6)
            payload["current_anomaly_score_mean"] = round(current_mean, 6)

    max_score = max(output_scores.values()) if output_scores else 0.0
    drifted_outputs = [output for output, score in output_scores.items() if score > drift_threshold]
    payload.update(
        {
            "drift_detected": bool(drifted_outputs),
            "max_drift_score": round(max_score, 6),
            "drifted_outputs": drifted_outputs,
            "output_scores": output_scores,
        }
    )
    return payload


def run_drift_detection(
    reference_path: str | Path | None = None,
    current_path: str | Path | None = None,
    report_path: str | Path | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    ensure_directories()
    reference = Path(reference_path or settings.model_dir / "training_reference.csv")
    current = Path(current_path or settings.feature_data_path)
    report = Path(report_path or settings.report_dir / "drift" / "latest_report.json")
    drift_threshold = settings.drift_threshold if threshold is None else threshold

    if not reference.exists():
        raise FileNotFoundError(f"Reference data not found: {reference}")
    if not current.exists():
        raise FileNotFoundError(f"Current data not found: {current}")

    reference_df = pd.read_csv(reference)
    current_df = pd.read_csv(current)
    feature_scores: dict[str, float] = {}
    for feature in FEATURE_COLUMNS:
        if feature in reference_df.columns and feature in current_df.columns:
            feature_scores[feature] = round(
                population_stability_index(reference_df[feature], current_df[feature]),
                6,
            )

    max_score = max(feature_scores.values()) if feature_scores else 0.0
    drifted_features = [feature for feature, score in feature_scores.items() if score > drift_threshold]
    payload = {
        "drift_detected": bool(drifted_features),
        "drift_threshold": drift_threshold,
        "max_drift_score": round(max_score, 6),
        "drifted_features": drifted_features,
        "feature_scores": feature_scores,
        "reference_path": str(reference),
        "current_path": str(current),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(run_drift_detection(), indent=2))
