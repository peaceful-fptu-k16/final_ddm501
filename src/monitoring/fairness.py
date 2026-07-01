from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.storage.prediction_logs import load_prediction_logs
from src.utils.config import ensure_directories, settings


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


def _load_logs(log_path: str | Path | None = None) -> pd.DataFrame:
    if log_path:
        source = Path(log_path)
        if not source.exists():
            raise FileNotFoundError(f"Prediction log does not exist: {source}")
        return pd.read_csv(source)
    return load_prediction_logs()


def _resolve_group_series(df: pd.DataFrame, group_column: str) -> tuple[pd.Series, str, str]:
    if group_column in df.columns:
        return df[group_column].fillna("unknown").astype(str), group_column, "configured_column"
    if "server_id" in df.columns:
        return df["server_id"].fillna("unknown").astype(str), "server_id", "fallback_server_id"
    return pd.Series(["all"] * len(df), index=df.index), "all", "single_group_fallback"


def _fairlearn_group_rates(predicted_anomaly: pd.Series, groups: pd.Series) -> dict[str, float] | None:
    try:
        from fairlearn.metrics import MetricFrame, selection_rate
    except ImportError:
        return None

    try:
        y_true = np.zeros(len(predicted_anomaly), dtype=int)
        metric_frame = MetricFrame(
            metrics={"anomaly_rate": selection_rate},
            y_true=y_true,
            y_pred=predicted_anomaly.astype(int).to_numpy(),
            sensitive_features=groups.astype(str).to_numpy(),
        )
        by_group = metric_frame.by_group
        if isinstance(by_group, pd.DataFrame):
            rates = by_group["anomaly_rate"].to_dict()
        else:
            rates = by_group.to_dict()
        return {str(group): round(float(rate), 6) for group, rate in rates.items()}
    except Exception:
        return None


def run_fairness_report(
    log_path: str | Path | None = None,
    report_path: str | Path | None = None,
    group_column: str | None = None,
    gap_threshold: float | None = None,
    minimum_group_size: int = 2,
) -> dict[str, Any]:
    ensure_directories()
    report = Path(report_path or settings.report_dir / "fairness" / "latest_report.json")
    selected_group_column = group_column or settings.fairness_group_column
    selected_gap_threshold = settings.fairness_gap_threshold if gap_threshold is None else gap_threshold

    try:
        df = _load_logs(log_path)
    except FileNotFoundError as exc:
        payload = {
            "status": "skipped",
            "reason": str(exc),
            "fairness_alert": False,
            "group_column": selected_group_column,
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    if df.empty:
        payload = {
            "status": "skipped",
            "reason": "Prediction log does not contain any rows",
            "fairness_alert": False,
            "group_column": selected_group_column,
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    required = {"prediction", "risk_level", "anomaly_score"}
    missing = sorted(required.difference(df.columns))
    if missing:
        payload = {
            "status": "skipped",
            "reason": f"Prediction log is missing required columns: {missing}",
            "fairness_alert": False,
            "group_column": selected_group_column,
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    groups, resolved_group_column, group_source = _resolve_group_series(df, selected_group_column)
    predicted_anomaly = df["prediction"].astype(str).str.lower().eq("anomaly")
    high_risk = df["risk_level"].astype(str).str.lower().eq("high")
    scores = pd.to_numeric(df["anomaly_score"], errors="coerce")

    fairlearn_rates = _fairlearn_group_rates(predicted_anomaly, groups)
    method = "fairlearn_metricframe" if fairlearn_rates is not None else "group_metric_parity"
    group_metrics: dict[str, dict[str, Any]] = {}
    for group_name, group_df in df.assign(_group=groups, _anomaly=predicted_anomaly, _high_risk=high_risk).groupby(
        "_group"
    ):
        group_scores = scores.loc[group_df.index].dropna()
        anomaly_rate = (
            fairlearn_rates.get(str(group_name), float(group_df["_anomaly"].mean()))
            if fairlearn_rates is not None
            else float(group_df["_anomaly"].mean())
        )
        group_metrics[str(group_name)] = {
            "request_count": int(len(group_df)),
            "anomaly_rate": round(float(anomaly_rate), 6),
            "high_risk_rate": round(float(group_df["_high_risk"].mean()), 6),
            "avg_anomaly_score": round(float(group_scores.mean()), 6) if not group_scores.empty else None,
        }

    eligible_rates = [
        metrics["anomaly_rate"]
        for metrics in group_metrics.values()
        if metrics["request_count"] >= minimum_group_size
    ]
    if eligible_rates:
        max_rate = max(eligible_rates)
        min_rate = min(eligible_rates)
        max_gap = max_rate - min_rate
        disparate_impact = (min_rate / max_rate) if max_rate > 0 else 1.0
    else:
        max_gap = 0.0
        disparate_impact = 1.0

    groups_below_minimum = [
        group for group, metrics in group_metrics.items() if metrics["request_count"] < minimum_group_size
    ]
    fairness_alert = bool(max_gap > selected_gap_threshold or disparate_impact < 0.8)

    payload = {
        "status": "completed",
        "method": method,
        "fairness_alert": fairness_alert,
        "group_column": resolved_group_column,
        "requested_group_column": selected_group_column,
        "group_source": group_source,
        "gap_threshold": round(float(selected_gap_threshold), 6),
        "minimum_group_size": minimum_group_size,
        "rows": int(len(df)),
        "overall_anomaly_rate": round(float(predicted_anomaly.mean()), 6),
        "overall_high_risk_rate": round(float(high_risk.mean()), 6),
        "max_anomaly_rate_gap": round(float(max_gap), 6),
        "disparate_impact_ratio": round(float(disparate_impact), 6),
        "groups_below_minimum_size": groups_below_minimum,
        "group_metrics": group_metrics,
        "note": (
            "This project has no human protected attributes in the prediction schema; "
            "the report measures parity over the configured operational segment."
        ),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")
    payload["report_path"] = str(report)
    return _json_ready(payload)


if __name__ == "__main__":
    print(json.dumps(run_fairness_report(), indent=2))
