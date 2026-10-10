from __future__ import annotations

from math import isclose
from typing import Any

from benchmark.metrics import set_scores
from benchmark.models import BenchmarkCase, CaseOutcome

from .base import Evaluator


class ResultEvaluator(Evaluator):
    suite = "result"

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        expected = case.expected.get("value")
        actual = case.input.get("actual")
        kind = case.expected.get("result_type", "scalar")
        tolerance = float(case.expected.get("tolerance", 0))
        metrics: dict[str, Any]
        if kind in {"scalar", "aggregation"}:
            passed = isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance)
            metrics = {f"{kind}_accuracy": float(passed)}
        elif kind == "set":
            metrics = set_scores(expected, actual)
            passed = metrics["f1"] == 1.0
        elif kind == "ranking":
            limit = min(len(expected), len(actual))
            matches = sum(expected[index] == actual[index] for index in range(limit))
            accuracy = matches / max(1, len(expected))
            metrics = {"ranking_accuracy": accuracy}
            passed = accuracy == 1.0
        elif kind == "grouped":
            keys = set(expected) | set(actual)
            matches = sum(key in expected and key in actual and isclose(float(expected[key]), float(actual[key]), rel_tol=tolerance, abs_tol=tolerance) for key in keys)
            accuracy = matches / max(1, len(keys))
            metrics = {"grouped_result_accuracy": accuracy}
            passed = accuracy == 1.0
        else:
            raise ValueError(f"unsupported result type: {kind}")
        score = float(metrics.get("f1", next((value for value in metrics.values() if isinstance(value, float)), 0)))
        return CaseOutcome(case_id=case.case_id, suite=self.suite, passed=passed, score=score, metrics=metrics, expected=case.expected, actual={"value": actual}, failure_type=None if passed else "RESULT_ERROR", stage="result")
