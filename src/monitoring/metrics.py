from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNTER = Counter("api_request_count", "Total prediction API requests")
ERROR_COUNTER = Counter("api_error_count", "Total prediction API errors")
LATENCY_HISTOGRAM = Histogram(
    "api_latency_seconds",
    "Prediction API latency",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
PREDICTION_COUNTER = Counter(
    "prediction_count",
    "Prediction count by class",
    labelnames=("prediction",),
)
ANOMALY_RATE_GAUGE = Gauge("prediction_anomaly_rate", "Rolling anomaly rate approximation")
DRIFT_SCORE_GAUGE = Gauge("drift_score", "Latest drift score")


def prometheus_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
