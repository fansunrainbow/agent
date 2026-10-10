from __future__ import annotations

from typing import Any, Iterable


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def set_scores(expected: Iterable[Any], actual: Iterable[Any]) -> dict[str, float | int]:
    expected_set, actual_set = set(expected), set(actual)
    if not expected_set and not actual_set:
        return {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(expected_set & actual_set)
    fp = len(actual_set - expected_set)
    fn = len(expected_set - actual_set)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def classification_counts(expected_positive: list[bool], actual_positive: list[bool]) -> dict[str, float | int]:
    tp = sum(e and a for e, a in zip(expected_positive, actual_positive))
    tn = sum(not e and not a for e, a in zip(expected_positive, actual_positive))
    fp = sum(not e and a for e, a in zip(expected_positive, actual_positive))
    fn = sum(e and not a for e, a in zip(expected_positive, actual_positive))
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": safe_div(tp + tn, len(expected_positive)),
        "precision": precision, "recall": recall,
        "f1": safe_div(2 * precision * recall, precision + recall),
    }
