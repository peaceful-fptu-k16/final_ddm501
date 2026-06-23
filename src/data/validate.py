from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.config import NUMERIC_RANGES, REQUIRED_RAW_COLUMNS, ensure_directories, settings


@dataclass
class DataQualityResult:
    valid: bool
    row_count: int
    errors: list[str]
    warnings: list[str]
    report_path: str


def _write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.suffix.lower() == ".html":
        rows = "\n".join(
            f"<tr><th>{key}</th><td><pre>{json.dumps(value, indent=2)}</pre></td></tr>"
            for key, value in report.items()
        )
        report_path.write_text(
            "<html><body><h1>Data Quality Report</h1><table>" + rows + "</table></body></html>",
            encoding="utf-8",
        )
    else:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def validate_raw_data(
    input_path: str | Path | None = None,
    report_path: str | Path | None = None,
    fail_on_error: bool = True,
) -> DataQualityResult:
    ensure_directories()
    source = Path(input_path or settings.raw_data_path)
    report = Path(report_path or settings.report_dir / "data_quality" / "latest_report.json")
    errors: list[str] = []
    warnings: list[str] = []

    if not source.exists():
        errors.append(f"Input file does not exist: {source}")
        payload = {
            "valid": False,
            "row_count": 0,
            "errors": errors,
            "warnings": warnings,
            "source": str(source),
        }
        _write_report(payload, report)
        if fail_on_error:
            raise FileNotFoundError(errors[0])
        return DataQualityResult(False, 0, errors, warnings, str(report))

    df = pd.read_csv(source)
    missing_columns = [column for column in REQUIRED_RAW_COLUMNS if column not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")

    if df.empty:
        errors.append("Dataset is empty")

    if "timestamp" in df.columns:
        invalid_timestamp_count = pd.to_datetime(df["timestamp"], errors="coerce").isna().sum()
        if invalid_timestamp_count:
            errors.append(f"Invalid timestamp values: {int(invalid_timestamp_count)}")

    if "server_id" in df.columns:
        missing_server_count = df["server_id"].isna().sum()
        if missing_server_count:
            errors.append(f"Missing server_id values: {int(missing_server_count)}")

    for column, (minimum, maximum) in NUMERIC_RANGES.items():
        if column not in df.columns:
            continue
        numeric = pd.to_numeric(df[column], errors="coerce")
        invalid_numeric = numeric.isna() & df[column].notna()
        if invalid_numeric.any():
            errors.append(f"Non-numeric values in {column}: {int(invalid_numeric.sum())}")
        non_finite = numeric.isin([float("inf"), float("-inf")])
        if non_finite.any():
            errors.append(f"Non-finite values in {column}: {int(non_finite.sum())}")
        missing_count = numeric.isna().sum()
        if missing_count:
            warnings.append(f"Missing values in {column}: {int(missing_count)}")
        if minimum is not None and (numeric < minimum).any():
            errors.append(f"{column} has values below {minimum}")
        if maximum is not None and (numeric > maximum).any():
            errors.append(f"{column} has values above {maximum}")

    duplicate_count = df.duplicated().sum()
    if duplicate_count:
        warnings.append(f"Duplicate rows: {int(duplicate_count)}")

    if {"timestamp", "server_id"}.issubset(df.columns):
        duplicate_event_count = df.duplicated(subset=["timestamp", "server_id"]).sum()
        if duplicate_event_count:
            warnings.append(f"Duplicate server events: {int(duplicate_event_count)}")

    if {"avg_latency_ms", "p95_latency_ms"}.issubset(df.columns):
        avg_latency = pd.to_numeric(df["avg_latency_ms"], errors="coerce")
        p95_latency = pd.to_numeric(df["p95_latency_ms"], errors="coerce")
        invalid_latency_order = p95_latency < avg_latency
        if invalid_latency_order.any():
            errors.append(f"p95_latency_ms below avg_latency_ms: {int(invalid_latency_order.sum())}")

    payload = {
        "valid": not errors,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "errors": errors,
        "warnings": warnings,
        "source": str(source),
    }
    _write_report(payload, report)

    result = DataQualityResult(not errors, int(len(df)), errors, warnings, str(report))
    if fail_on_error and errors:
        raise ValueError("; ".join(errors))
    return result


def validate_raw_data_as_dict(
    input_path: str | Path | None = None,
    report_path: str | Path | None = None,
    fail_on_error: bool = True,
) -> dict[str, Any]:
    return asdict(validate_raw_data(input_path, report_path, fail_on_error))
