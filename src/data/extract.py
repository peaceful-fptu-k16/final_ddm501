from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import ensure_directories, settings


def generate_synthetic_metrics(rows: int = 720, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(end=pd.Timestamp.utcnow().floor("min"), periods=rows, freq="5min")
    servers = np.array([f"srv-{idx:02d}" for idx in range(1, 6)])

    server_id = rng.choice(servers, size=rows)
    hour = timestamps.hour.to_numpy()
    business_load = 1.0 + 0.35 * ((hour >= 8) & (hour <= 18))

    cpu_usage = rng.normal(45 * business_load, 12, rows)
    memory_usage = rng.normal(58 * business_load, 10, rows)
    request_count = rng.poisson(140 * business_load, rows).astype(float)
    error_rate = rng.beta(1.5, 60, rows)
    avg_latency_ms = rng.normal(220 * business_load, 60, rows)
    p95_latency_ms = avg_latency_ms + rng.normal(120, 45, rows)

    is_anomaly = rng.random(rows) < 0.06
    spike = rng.uniform(1.4, 2.4, rows)
    cpu_usage[is_anomaly] += 35 * spike[is_anomaly]
    memory_usage[is_anomaly] += 25 * spike[is_anomaly]
    request_count[is_anomaly] += rng.poisson(260, is_anomaly.sum())
    error_rate[is_anomaly] += rng.uniform(0.12, 0.38, is_anomaly.sum())
    avg_latency_ms[is_anomaly] += rng.uniform(650, 1600, is_anomaly.sum())
    p95_latency_ms[is_anomaly] += rng.uniform(900, 2200, is_anomaly.sum())

    df = pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "server_id": server_id,
            "cpu_usage": np.clip(cpu_usage, 0, 100).round(2),
            "memory_usage": np.clip(memory_usage, 0, 100).round(2),
            "request_count": np.maximum(request_count, 0).round(0).astype(int),
            "error_rate": np.clip(error_rate, 0, 1).round(4),
            "avg_latency_ms": np.maximum(avg_latency_ms, 1).round(2),
            "p95_latency_ms": np.maximum(p95_latency_ms, 1).round(2),
            "is_anomaly": is_anomaly.astype(int),
        }
    )
    return df


def extract_server_metrics(source_path: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    ensure_directories()
    output = Path(output_path or settings.raw_data_path)

    if source_path:
        df = pd.read_csv(source_path)
    else:
        df = generate_synthetic_metrics()

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return output


if __name__ == "__main__":
    print(extract_server_metrics())
