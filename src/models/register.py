from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.utils.config import ensure_directories, settings


MODEL_FILES = [
    "model.joblib",
    "scaler.joblib",
    "feature_columns.json",
    "metrics.json",
    "training_reference.csv",
]


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _is_better(candidate: dict[str, Any], current: dict[str, Any] | None) -> bool:
    if current is None:
        return True
    candidate_f1 = float(candidate.get("f1_score", 0.0))
    current_f1 = float(current.get("f1_score", 0.0))
    candidate_recall = float(candidate.get("recall", 0.0))
    candidate_fpr = float(candidate.get("false_positive_rate", 1.0))
    return candidate_f1 > current_f1 and candidate_recall >= 0.75 and candidate_fpr <= 0.1


def register_model_if_better(
    model_dir: str | Path | None = None,
    registry_dir: str | Path | None = None,
    stage: str = "Production",
) -> dict[str, Any]:
    ensure_directories()
    source_dir = Path(model_dir or settings.model_dir)
    registry = Path(registry_dir or settings.registry_dir)
    registry.mkdir(parents=True, exist_ok=True)
    state_path = registry / "registry_state.json"

    metrics_path = source_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing metrics file: {metrics_path}")

    candidate_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    state = _load_json(state_path, {"models": [], "production_version": None})
    current_metrics = None
    if state.get("production_version"):
        current_dir = registry / state["production_version"]
        current_metrics = _load_json(current_dir / "metrics.json", {})

    should_register = _is_better(candidate_metrics, current_metrics)
    if not should_register:
        return {
            "registered": False,
            "reason": "Candidate model did not pass promotion gates",
            "candidate_metrics": candidate_metrics,
            "current_metrics": current_metrics,
        }

    version_number = len(state["models"]) + 1
    version = f"v{version_number}"
    version_dir = registry / version
    version_dir.mkdir(parents=True, exist_ok=True)

    for filename in MODEL_FILES:
        source = source_dir / filename
        if source.exists():
            shutil.copy2(source, version_dir / filename)

    (version_dir / "stage.txt").write_text(stage, encoding="utf-8")
    (version_dir / "version.txt").write_text(version, encoding="utf-8")
    shutil.copy2(version_dir / "version.txt", source_dir / "version.txt")

    state["models"].append(
        {
            "version": version,
            "stage": stage,
            "metrics": candidate_metrics,
        }
    )
    state["production_version"] = version if stage == "Production" else state.get("production_version")
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    return {
        "registered": True,
        "version": version,
        "stage": stage,
        "metrics": candidate_metrics,
    }


if __name__ == "__main__":
    print(json.dumps(register_model_if_better(), indent=2))
