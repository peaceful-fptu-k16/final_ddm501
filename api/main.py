from __future__ import annotations

import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request, Response

from api.model_loader import ModelBundle
from api.schemas import DetectionRequest, DetectionResponse
from api.security import require_api_key
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
from src.utils.structured_logging import configure_logging

configure_logging()
logger = logging.getLogger("server_log_anomaly.api")
app = FastAPI(title="Server Log Anomaly Detection API", version="0.1.0")
bundle = ModelBundle()
prediction_window: list[int] = []


def _payload_to_dict(payload: DetectionRequest) -> dict[str, object]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
            },
        )
        raise

    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 3),
        },
    )
    return response


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": bundle.loaded,
        "model_version": bundle.version,
        "model_source": bundle.source,
    }


@app.post("/detect", response_model=DetectionResponse, dependencies=[Depends(require_api_key)])
def detect(payload: DetectionRequest, request: Request) -> DetectionResponse:
    REQUEST_COUNTER.inc()
    start = time.perf_counter()
    data = _payload_to_dict(payload)
    try:
        result = bundle.predict(data)
        PREDICTION_COUNTER.labels(prediction=str(result["prediction"])).inc()
        prediction_window.append(1 if result["prediction"] == "anomaly" else 0)
        del prediction_window[:-100]
        ANOMALY_RATE_GAUGE.set(sum(prediction_window) / max(len(prediction_window), 1))
        append_prediction_log(data, result, request_id=request.state.request_id)
        logger.info(
            "prediction_completed",
            extra={
                "request_id": request.state.request_id,
                "server_id": data["server_id"],
                "prediction": result["prediction"],
                "risk_level": result["risk_level"],
                "model_version": result["model_version"],
            },
        )
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


@app.post("/drift", dependencies=[Depends(require_api_key)])
def drift() -> dict[str, object]:
    report = run_production_drift_detection()
    DRIFT_SCORE_GAUGE.set(float(report.get("max_drift_score", 0.0)))
    return report
