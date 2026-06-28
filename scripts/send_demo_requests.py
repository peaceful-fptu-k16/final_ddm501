from __future__ import annotations

import argparse
import os
import random
import time

import requests


NORMAL_PAYLOADS = [
    {
        "server_id": "srv-01",
        "cpu_usage": 42.0,
        "memory_usage": 55.0,
        "request_count": 150,
        "error_rate": 0.015,
        "avg_latency_ms": 220,
        "p95_latency_ms": 360,
    },
    {
        "server_id": "srv-02",
        "cpu_usage": 58.0,
        "memory_usage": 62.0,
        "request_count": 180,
        "error_rate": 0.025,
        "avg_latency_ms": 260,
        "p95_latency_ms": 430,
    },
]

ANOMALY_PAYLOADS = [
    {
        "server_id": "srv-01",
        "cpu_usage": 94.0,
        "memory_usage": 91.0,
        "request_count": 520,
        "error_rate": 0.32,
        "avg_latency_ms": 1700,
        "p95_latency_ms": 2600,
    },
    {
        "server_id": "srv-03",
        "cpu_usage": 88.0,
        "memory_usage": 84.0,
        "request_count": 470,
        "error_rate": 0.24,
        "avg_latency_ms": 1350,
        "p95_latency_ms": 2100,
    },
]


def send_requests(
    api_url: str,
    rounds: int,
    delay_seconds: float,
    api_key: str | None = None,
    anomaly_probability: float = 0.1,
    seed: int | None = None,
) -> None:
    headers = {"X-API-Key": api_key} if api_key else {}
    rng = random.Random(seed)
    for index in range(rounds):
        expected_class = "anomaly" if rng.random() < anomaly_probability else "normal"
        payloads = ANOMALY_PAYLOADS if expected_class == "anomaly" else NORMAL_PAYLOADS
        payload = rng.choice(payloads)
        response = requests.post(f"{api_url.rstrip('/')}/detect", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"{index + 1:03d} {expected_class:7s} {payload['server_id']} -> {response.json()}")
        if delay_seconds:
            time.sleep(delay_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send demo requests to the anomaly detection API.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=os.getenv("API_KEY", "ddm501-demo-api-key"))
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--anomaly-probability", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if not 0 <= args.anomaly_probability <= 1:
        parser.error("--anomaly-probability must be between 0 and 1")
    send_requests(args.api_url, args.rounds, args.delay_seconds, args.api_key, args.anomaly_probability, args.seed)


if __name__ == "__main__":
    main()
