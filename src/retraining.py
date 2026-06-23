from __future__ import annotations

import json
from typing import Any

from src.monitoring.production import run_production_drift_detection
from src.pipeline import run_training_pipeline


def trigger_retraining_if_needed(threshold: float | None = None) -> dict[str, Any]:
    drift = run_production_drift_detection(threshold=threshold)
    if not drift.get("drift_detected"):
        return {
            "retraining_triggered": False,
            "reason": drift.get("reason", "No drift above threshold"),
            "drift": drift,
        }

    pipeline_result = run_training_pipeline()
    return {
        "retraining_triggered": True,
        "reason": "Production drift exceeded threshold",
        "drift": drift,
        "pipeline_result": pipeline_result,
    }


if __name__ == "__main__":
    print(json.dumps(trigger_retraining_if_needed(), indent=2))
