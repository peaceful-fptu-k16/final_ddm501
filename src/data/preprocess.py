from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.validate import validate_raw_data
from src.utils.config import NUMERIC_RANGES, ensure_directories, settings


def preprocess_data(input_path: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    ensure_directories()
    source = Path(input_path or settings.raw_data_path)
    output = Path(output_path or settings.processed_data_path)

    validate_raw_data(source, fail_on_error=True)
    df = pd.read_csv(source)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "server_id"]).drop_duplicates()
    df = df.sort_values(["server_id", "timestamp"]).reset_index(drop=True)

    for column, (minimum, maximum) in NUMERIC_RANGES.items():
        df[column] = pd.to_numeric(df[column], errors="coerce")
        fill_value = df[column].median()
        if pd.isna(fill_value):
            fill_value = 0.0
        df[column] = df[column].fillna(fill_value)
        if minimum is not None:
            df[column] = df[column].clip(lower=minimum)
        if maximum is not None:
            df[column] = df[column].clip(upper=maximum)

    if "is_anomaly" in df.columns:
        df["is_anomaly"] = pd.to_numeric(df["is_anomaly"], errors="coerce").fillna(0).astype(int)

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return output


if __name__ == "__main__":
    print(preprocess_data())
