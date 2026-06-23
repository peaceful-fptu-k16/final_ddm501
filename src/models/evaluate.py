from __future__ import annotations

from typing import Iterable

import numpy as np


def isolation_predictions_to_binary(predictions: Iterable[int]) -> np.ndarray:
    values = np.asarray(list(predictions))
    return (values == -1).astype(int)


def evaluate_predictions(y_true: Iterable[int], isolation_predictions: Iterable[int]) -> dict[str, float]:
    truth = np.asarray(list(y_true)).astype(int)
    predicted = isolation_predictions_to_binary(isolation_predictions)

    if truth.size != predicted.size:
        raise ValueError("y_true and predictions must have the same length")

    tp = float(((truth == 1) & (predicted == 1)).sum())
    fp = float(((truth == 0) & (predicted == 1)).sum())
    fn = float(((truth == 1) & (predicted == 0)).sum())
    tn = float(((truth == 0) & (predicted == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    anomaly_rate = float(predicted.mean()) if predicted.size else 0.0

    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1_score": round(f1_score, 6),
        "false_positive_rate": round(false_positive_rate, 6),
        "anomaly_rate": round(anomaly_rate, 6),
    }
