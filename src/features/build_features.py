from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import BASE_FEATURES, FEATURE_COLUMNS, ensure_directories, settings


def create_features(input_path: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    ensure_directories()
    source = Path(input_path or settings.processed_data_path)
    output = Path(output_path or settings.feature_data_path)

    df = pd.read_csv(source)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values(["server_id", "timestamp"]).reset_index(drop=True)

    for column in BASE_FEATURES:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
        df[f"{column}_roll_mean_3"] = (
            df.groupby("server_id", group_keys=False)[column]
            .transform(lambda values: values.rolling(window=3, min_periods=1).mean())
            .fillna(df[column])
        )

    df["latency_error_interaction"] = df["avg_latency_ms"] * (1.0 + df["error_rate"])
    df["traffic_error_pressure"] = df["request_count"] * (1.0 + 10.0 * df["error_rate"])

    missing = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing engineered feature columns: {missing}")

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    (output.parent / "feature_columns.json").write_text(json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(create_features())
