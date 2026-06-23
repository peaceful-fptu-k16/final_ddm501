from __future__ import annotations

import argparse
import itertools
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


def send_requests(api_url: str, rounds: int, delay_seconds: float) -> None:
    payloads = NORMAL_PAYLOADS + ANOMALY_PAYLOADS
    for index, payload in zip(range(rounds), itertools.cycle(payloads)):
        response = requests.post(f"{api_url.rstrip('/')}/detect", json=payload, timeout=10)
        response.raise_for_status()
        print(f"{index + 1:03d} {payload['server_id']} -> {response.json()}")
        if delay_seconds:
            time.sleep(delay_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send demo requests to the anomaly detection API.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--delay-seconds", type=float, default=0.1)
    args = parser.parse_args()
    send_requests(args.api_url, args.rounds, args.delay_seconds)


if __name__ == "__main__":
    main()
