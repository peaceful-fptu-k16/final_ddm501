from src.models.evaluate import evaluate_predictions


def test_evaluate_predictions_computes_metrics() -> None:
    metrics = evaluate_predictions([0, 0, 1, 1], [1, -1, -1, 1])

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1_score"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
