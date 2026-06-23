from __future__ import annotations

import time

from fastapi import FastAPI, Response

from api.model_loader import ModelBundle
from api.schemas import DetectionRequest, DetectionResponse
from src.monitoring.metrics import (
    ANOMALY_RATE_GAUGE,
    DRIFT_SCORE_GAUGE,
    ERROR_COUNTER,
    LATENCY_HISTOGRAM,
    PREDICTION_COUNTER,
    REQUEST_COUNTER,
    prometheus_response,
)
from src.monitoring.production import run_production_drift_detection
from src.storage.prediction_logs import append_prediction_log

app = FastAPI(title="Server Log Anomaly Detection API", version="0.1.0")
bundle = ModelBundle()
prediction_window: list[int] = []


def _payload_to_dict(payload: DetectionRequest) -> dict[str, object]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": bundle.loaded,
        "model_version": bundle.version,
        "model_source": bundle.source,
    }


@app.post("/detect", response_model=DetectionResponse)
def detect(payload: DetectionRequest) -> DetectionResponse:
    REQUEST_COUNTER.inc()
    start = time.perf_counter()
    data = _payload_to_dict(payload)
    try:
        result = bundle.predict(data)
        PREDICTION_COUNTER.labels(prediction=str(result["prediction"])).inc()
        prediction_window.append(1 if result["prediction"] == "anomaly" else 0)
        del prediction_window[:-100]
        ANOMALY_RATE_GAUGE.set(sum(prediction_window) / max(len(prediction_window), 1))
        append_prediction_log(data, result)
        return DetectionResponse(**result)
    except Exception:
        ERROR_COUNTER.inc()
        raise
    finally:
        LATENCY_HISTOGRAM.observe(time.perf_counter() - start)


@app.get("/metrics")
def metrics() -> Response:
    payload, content_type = prometheus_response()
    return Response(content=payload, media_type=content_type)


@app.post("/drift")
def drift() -> dict[str, object]:
    report = run_production_drift_detection()
    DRIFT_SCORE_GAUGE.set(float(report.get("max_drift_score", 0.0)))
    return report
