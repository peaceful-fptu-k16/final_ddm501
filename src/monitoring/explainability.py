from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import BASE_FEATURES, ensure_directories, settings


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value


def _vector_frame(bundle: Any, payload: dict[str, Any]) -> pd.DataFrame:
    vector = bundle._vectorize(payload)  # noqa: SLF001 - internal API helper used by monitoring reports.
    return pd.DataFrame(vector, columns=bundle.feature_columns)


def _prediction_score(bundle: Any, frame: pd.DataFrame, payload: dict[str, Any]) -> float:
    if not bundle.loaded:
        return float(bundle.predict(payload)["anomaly_score"])

    if bundle.source == "mlflow":
        model = bundle.model
        if hasattr(model, "decision_function"):
            return float(model.decision_function(frame)[0])
        return float(bundle.predict(payload)["anomaly_score"])

    scaled = bundle.scaler.transform(frame)
    return float(bundle.model.decision_function(scaled)[0])


def _load_reference_median(bundle: Any) -> pd.Series:
    candidates = [
        Path(bundle.model_dir) / "training_reference.csv",
        settings.model_dir / "training_reference.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            reference = pd.read_csv(candidate)
            available = [feature for feature in bundle.feature_columns if feature in reference.columns]
            if available:
                return reference[available].median(numeric_only=True)
    return pd.Series({feature: 0.0 for feature in bundle.feature_columns})


def _direction_from_impact(impact: float) -> str:
    if impact > 0:
        return "raises_anomaly_risk"
    if impact < 0:
        return "lowers_anomaly_risk"
    return "neutral"


def _format_feature_impacts(frame: pd.DataFrame, impacts: dict[str, float], top_n: int) -> list[dict[str, Any]]:
    rows = []
    values = frame.iloc[0].to_dict()
    for feature, impact in sorted(impacts.items(), key=lambda item: abs(item[1]), reverse=True)[:top_n]:
        rows.append(
            {
                "feature": feature,
                "value": round(float(values.get(feature, 0.0)), 6),
                "impact": round(float(impact), 6),
                "abs_impact": round(abs(float(impact)), 6),
                "direction": _direction_from_impact(float(impact)),
            }
        )
    return rows


def _shap_impacts(bundle: Any, frame: pd.DataFrame) -> dict[str, float] | None:
    if not bundle.loaded:
        return None

    try:
        import shap
    except ImportError:
        return None

    try:
        model = bundle.model
        model_input: Any = frame
        if bundle.source == "mlflow" and hasattr(model, "named_steps"):
            scaler = model.named_steps.get("scaler")
            estimator = model.named_steps.get("model")
            if scaler is not None and estimator is not None:
                model_input = scaler.transform(frame)
                model = estimator
        elif bundle.source != "mlflow":
            model_input = bundle.scaler.transform(frame)

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(model_input)
        values = shap_values[0] if isinstance(shap_values, list) else shap_values
        row_values = np.asarray(values)[0]
        return {
            feature: -float(value)
            for feature, value in zip(bundle.feature_columns, row_values, strict=False)
        }
    except Exception:
        return None


def _permutation_impacts(bundle: Any, payload: dict[str, Any], frame: pd.DataFrame) -> dict[str, float]:
    reference = _load_reference_median(bundle)
    original_score = _prediction_score(bundle, frame, payload)
    impacts: dict[str, float] = {}

    for feature in bundle.feature_columns:
        perturbed = frame.copy()
        perturbed.loc[0, feature] = float(reference.get(feature, 0.0))
        perturbed_payload = dict(payload)
        for base_feature in BASE_FEATURES:
            if base_feature in perturbed.columns:
                perturbed_payload[base_feature] = float(perturbed.loc[0, base_feature])
        perturbed_score = _prediction_score(bundle, perturbed, perturbed_payload)
        impacts[feature] = perturbed_score - original_score

    return impacts


def explain_prediction(
    bundle: Any,
    payload: dict[str, Any],
    top_n: int = 8,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_directories()
    frame = _vector_frame(bundle, payload)
    prediction = bundle.predict(payload)

    impacts = _shap_impacts(bundle, frame)
    method = "shap_tree_explainer"
    if impacts is None:
        impacts = _permutation_impacts(bundle, payload, frame)
        method = "permutation_reference_delta"

    report = {
        "status": "completed",
        "method": method,
        "model_version": prediction["model_version"],
        "model_source": bundle.source,
        "prediction": prediction["prediction"],
        "anomaly_score": prediction["anomaly_score"],
        "risk_level": prediction["risk_level"],
        "top_features": _format_feature_impacts(frame, impacts, top_n),
        "feature_impacts": {feature: round(float(value), 6) for feature, value in impacts.items()},
        "request": {key: payload[key] for key in ["server_id", *BASE_FEATURES] if key in payload},
    }

    output = Path(report_path or settings.report_dir / "explainability" / "latest_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_json_ready(report), indent=2), encoding="utf-8")
    report["report_path"] = str(output)
    return _json_ready(report)
