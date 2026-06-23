from src import retraining


def test_retraining_skips_when_no_drift(monkeypatch) -> None:
    monkeypatch.setattr(
        retraining,
        "run_production_drift_detection",
        lambda threshold=None: {"drift_detected": False, "reason": "No drift"},
    )

    result = retraining.trigger_retraining_if_needed()

    assert result["retraining_triggered"] is False
    assert result["reason"] == "No drift"


def test_retraining_runs_pipeline_when_drift_detected(monkeypatch) -> None:
    monkeypatch.setattr(
        retraining,
        "run_production_drift_detection",
        lambda threshold=None: {"drift_detected": True, "max_drift_score": 0.5},
    )
    monkeypatch.setattr(retraining, "run_training_pipeline", lambda: {"status": "trained"})

    result = retraining.trigger_retraining_if_needed()

    assert result["retraining_triggered"] is True
    assert result["pipeline_result"] == {"status": "trained"}
