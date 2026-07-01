from __future__ import annotations

import logging
import time
import uuid
from threading import RLock

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

from api.model_loader import ModelBundle
from api.schemas import DetectionRequest, DetectionResponse, FairnessRequest, RetrainRequest
from api.security import require_api_key
from src.monitoring.explainability import explain_prediction
from src.monitoring.fairness import run_fairness_report
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
from src.pipeline import run_training_pipeline
from src.retraining import trigger_retraining_if_needed
from src.storage.prediction_logs import append_prediction_log
from src.utils.config import settings
from src.utils.structured_logging import configure_logging

configure_logging()
logger = logging.getLogger("server_log_anomaly.api")
app = FastAPI(title="Server Log Anomaly Detection API", version="0.1.0")
bundle = ModelBundle()
bundle_lock = RLock()
prediction_window: list[int] = []


def _payload_to_dict(payload: DetectionRequest) -> dict[str, object]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def _bundle_state(model_bundle: ModelBundle) -> dict[str, object]:
    return {
        "model_loaded": model_bundle.loaded,
        "model_version": model_bundle.version,
        "model_source": model_bundle.source,
        "model_load_error": model_bundle.load_error,
    }


def _reload_model_bundle() -> dict[str, object]:
    global bundle

    with bundle_lock:
        previous = _bundle_state(bundle)
    candidate = ModelBundle()
    if not candidate.loaded:
        return {
            "reloaded": False,
            "previous": previous,
            "current": _bundle_state(candidate),
        }

    with bundle_lock:
        bundle = candidate
        current = _bundle_state(bundle)

    logger.info(
        "model_reloaded",
        extra={
            "previous_model_version": previous["model_version"],
            "current_model_version": current["model_version"],
            "current_model_source": current["model_source"],
        },
    )
    return {
        "reloaded": True,
        "previous": previous,
        "current": current,
    }


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
    with bundle_lock:
        return {
            "status": "ok",
            "model_loaded": bundle.loaded,
            "model_version": bundle.version,
            "model_source": bundle.source,
            "model_load_error": bundle.load_error,
        }


@app.post("/model/reload", dependencies=[Depends(require_api_key)])
def reload_model() -> dict[str, object]:
    reload_result = _reload_model_bundle()
    if settings.mlflow_model_uri and reload_result["current"]["model_source"] != "mlflow":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Failed to reload production model from MLflow",
                "previous": reload_result["previous"],
                "load_error": reload_result["current"]["model_load_error"],
            },
        )
    if not reload_result["reloaded"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Reloaded bundle has no loaded model",
                "previous": reload_result["previous"],
                "load_error": reload_result["current"]["model_load_error"],
            },
        )
    return {
        "status": "reloaded",
        "previous": reload_result["previous"],
        "current": reload_result["current"],
    }


@app.post("/detect", response_model=DetectionResponse, dependencies=[Depends(require_api_key)])
def detect(payload: DetectionRequest, request: Request) -> DetectionResponse:
    REQUEST_COUNTER.inc()
    start = time.perf_counter()
    data = _payload_to_dict(payload)
    try:
        with bundle_lock:
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


@app.post("/explain", dependencies=[Depends(require_api_key)])
def explain(payload: DetectionRequest) -> dict[str, object]:
    data = _payload_to_dict(payload)
    with bundle_lock:
        return explain_prediction(bundle, data)


@app.get("/metrics")
def metrics() -> Response:
    payload, content_type = prometheus_response()
    return Response(content=payload, media_type=content_type)


@app.post("/drift", dependencies=[Depends(require_api_key)])
def drift() -> dict[str, object]:
    report = run_production_drift_detection()
    DRIFT_SCORE_GAUGE.set(float(report.get("max_drift_score", 0.0)))
    return report


@app.post("/fairness", dependencies=[Depends(require_api_key)])
def fairness(payload: FairnessRequest | None = None) -> dict[str, object]:
    request_payload = payload or FairnessRequest()
    return run_fairness_report(
        group_column=request_payload.group_column,
        gap_threshold=request_payload.gap_threshold,
    )


@app.post("/retrain", dependencies=[Depends(require_api_key)])
def retrain(payload: RetrainRequest | None = None) -> dict[str, object]:
    request_payload = payload or RetrainRequest()
    if request_payload.force:
        result = {
            "retraining_triggered": True,
            "reason": "Forced retraining requested via API",
            "pipeline_result": run_training_pipeline(),
        }
    else:
        result = trigger_retraining_if_needed(threshold=request_payload.drift_threshold)

    if request_payload.reload_after_train and result.get("retraining_triggered"):
        result["model_reload"] = _reload_model_bundle()
    return result
