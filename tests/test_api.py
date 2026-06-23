from fastapi.testclient import TestClient

from api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_detect_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        "/detect",
        json={
            "server_id": "srv-01",
            "cpu_usage": 92.5,
            "memory_usage": 88.1,
            "request_count": 420,
            "error_rate": 0.27,
            "avg_latency_ms": 1600,
            "p95_latency_ms": 2400,
        },
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
