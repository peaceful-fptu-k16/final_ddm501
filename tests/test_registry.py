import json
from pathlib import Path

from src.models.register import promote_model_version, register_model_if_better, rollback_production_model


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


def test_rollback_production_model_updates_registry_state(tmp_path: Path) -> None:
    registry_dir = tmp_path / "registry"
    model_dir = tmp_path / "latest"
    for version in ["v1", "v2"]:
        version_dir = registry_dir / version
        version_dir.mkdir(parents=True)
        (version_dir / "metrics.json").write_text(json.dumps({"f1_score": 0.9}), encoding="utf-8")
        (version_dir / "version.txt").write_text(version, encoding="utf-8")

    (registry_dir / "registry_state.json").write_text(
        json.dumps(
            {
                "models": [
                    {"version": "v1", "stage": "Archived", "metrics": {"f1_score": 0.88}},
                    {"version": "v2", "stage": "Production", "metrics": {"f1_score": 0.9}},
                ],
                "production_version": "v2",
            }
        ),
        encoding="utf-8",
    )

    rollback = rollback_production_model("v1", registry_dir=registry_dir, model_dir=model_dir)
    promote = promote_model_version("v2", registry_dir=registry_dir, model_dir=model_dir)

    assert rollback["production_version"] == "v1"
    assert promote["production_version"] == "v2"
    assert (model_dir / "version.txt").read_text(encoding="utf-8") == "v2"
