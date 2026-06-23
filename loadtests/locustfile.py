from __future__ import annotations

import os

from locust import HttpUser, between, task

NORMAL_PAYLOAD = {
    "server_id": "srv-load-01",
    "cpu_usage": 42.0,
    "memory_usage": 58.0,
    "request_count": 180,
    "error_rate": 0.02,
    "avg_latency_ms": 260,
    "p95_latency_ms": 420,
}

ANOMALY_PAYLOAD = {
    "server_id": "srv-load-02",
    "cpu_usage": 96.0,
    "memory_usage": 91.0,
    "request_count": 720,
    "error_rate": 0.31,
    "avg_latency_ms": 1700,
    "p95_latency_ms": 2600,
}


class PredictionUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        api_key = os.getenv("API_KEY")
        self.headers = {"X-API-Key": api_key} if api_key else {}

    @task(4)
    def normal_prediction(self) -> None:
        self.client.post("/detect", json=NORMAL_PAYLOAD, headers=self.headers, name="/detect normal")

    @task(1)
    def anomalous_prediction(self) -> None:
        self.client.post("/detect", json=ANOMALY_PAYLOAD, headers=self.headers, name="/detect anomaly")

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="/health")
