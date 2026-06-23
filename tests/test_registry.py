import json
from pathlib import Path

from src.models.register import register_model_if_better


def test_register_model_requires_better_f1_for_existing_production(tmp_path: Path) -> None:
    model_dir = tmp_path / "latest"
    registry_dir = tmp_path / "registry"
    model_dir.mkdir()
    metrics = {
        "precision": 0.9,
        "recall": 0.9,
        "f1_score": 0.9,
        "false_positive_rate": 0.05,
    }
    (model_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    first = register_model_if_better(model_dir, registry_dir)
    second = register_model_if_better(model_dir, registry_dir)

    assert first["registered"] is True
    assert second["registered"] is False
    state = json.loads((registry_dir / "registry_state.json").read_text(encoding="utf-8"))
    assert len(state["models"]) == 1
