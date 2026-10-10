from __future__ import annotations

from time import perf_counter

from benchmark.models import BenchmarkCase, CaseOutcome
from guardrail.sql_validator import SQLValidator

from .base import Evaluator


class GuardrailEvaluator(Evaluator):
    suite = "guardrail"

    def __init__(self):
        self.validator = SQLValidator()

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        report = self.validator.validate(case.input["sql"])
        action = "block" if not report.allowed else ("warn" if any(issue.severity == "warning" for issue in report.issues) else "allow")
        expected_action = case.expected["action"]
        passed = action == expected_action
        unsafe = expected_action == "block"
        return CaseOutcome(
            case_id=case.case_id, suite=self.suite, passed=passed, score=float(passed),
            metrics={
                "expected_unsafe": float(unsafe), "blocked": float(action == "block"),
                "unsafe_correctly_blocked": float(unsafe and action == "block"),
                "safe_correctly_passed": float(not unsafe and action == "allow"),
                "false_positive": float(not unsafe and action == "block"),
                "false_negative": float(unsafe and action != "block"),
            },
            expected=case.expected, actual={"action": action, "issues": [item.to_dict() for item in report.issues]},
            latency_ms={"guardrail": round((perf_counter() - started) * 1000, 3)},
            failure_type=None if passed else ("COST_GUARD_ERROR" if any(item.code in {"FACT_TIME_FILTER_REQUIRED", "LIMIT_EXCEEDED"} for item in report.issues) else "SCHEMA_GUARD_ERROR"),
            stage="guardrail",
        )
