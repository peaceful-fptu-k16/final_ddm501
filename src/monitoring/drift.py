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
