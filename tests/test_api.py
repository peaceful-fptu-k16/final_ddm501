from fastapi.testclient import TestClient

from api import main as api_main
from api.main import app
from src.utils.config import settings

DETECTION_PAYLOAD = {
    "server_id": "srv-01",
    "cpu_usage": 92.5,
    "memory_usage": 88.1,
    "request_count": 420,
    "error_rate": 0.27,
    "avg_latency_ms": 1600,
    "p95_latency_ms": 2400,
}


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_detect_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        "/detect",
        json=DETECTION_PAYLOAD,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction"] in {"normal", "anomaly"}
    assert "model_version" in payload


def test_drift_endpoint() -> None:
    client = TestClient(app)
    response = client.post("/drift")

    assert response.status_code == 200
    assert "drift_detected" in response.json()


def test_explain_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "explain_prediction",
        lambda model_bundle, data: {
            "status": "completed",
            "prediction": "anomaly",
            "top_features": [{"feature": "error_rate", "impact": 0.3}],
        },
    )
    client = TestClient(app)
    response = client.post("/explain", json=DETECTION_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["top_features"][0]["feature"] == "error_rate"


def test_fairness_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "run_fairness_report",
        lambda group_column=None, gap_threshold=None: {
            "status": "completed",
            "fairness_alert": False,
            "group_column": group_column or "server_id",
        },
    )
    client = TestClient(app)
    response = client.post("/fairness", json={"group_column": "server_id"})

    assert response.status_code == 200
    assert response.json()["group_column"] == "server_id"


def test_retrain_endpoint_checks_trigger(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "trigger_retraining_if_needed",
        lambda threshold=None: {"retraining_triggered": False, "reason": "No drift"},
    )
    client = TestClient(app)
    response = client.post("/retrain", json={"force": False})

    assert response.status_code == 200
    assert response.json()["retraining_triggered"] is False


def test_detect_endpoint_rejects_invalid_latency_order() -> None:
    client = TestClient(app)
    response = client.post(
        "/detect",
        json={
            "server_id": "srv-01",
            "cpu_usage": 50.0,
            "memory_usage": 55.0,
            "request_count": 100,
            "error_rate": 0.01,
            "avg_latency_ms": 500,
            "p95_latency_ms": 300,
        },
    )

    assert response.status_code == 422


def test_detect_endpoint_requires_api_key_when_configured() -> None:
    client = TestClient(app)
    previous_key = settings.api_key
    object.__setattr__(settings, "api_key", "test-secret")
    try:
        payload = {
            **DETECTION_PAYLOAD,
        }
        unauthorized = client.post("/detect", json=payload)
        authorized = client.post("/detect", json=payload, headers={"X-API-Key": "test-secret"})
    finally:
        object.__setattr__(settings, "api_key", previous_key)

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.headers["X-Request-ID"]
