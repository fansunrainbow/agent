from __future__ import annotations

from time import perf_counter
from typing import Any

from benchmark.models import BenchmarkCase, CaseOutcome
from guardrail.sql_generator import SQLGenerationError, SQLGenerator
from guardrail.sql_validator import SQLValidator
from scripts.validate_query_plan import validate_plan_data

from .base import Evaluator


class SQLEvaluator(Evaluator):
    suite = "sql"

    def __init__(self):
        self.generator = SQLGenerator()
        self.validator = SQLValidator()

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        plan = case.input.get("plan") or case.expected.get("plan")
        started = perf_counter()
        compile_success = False
        actual: dict[str, Any] = {}
        try:
            validation = validate_plan_data(plan)
            artifact = self.generator.generate(case.case_id, plan, validation)
            compile_ms = (perf_counter() - started) * 1000
            guard_started = perf_counter()
            report = self.validator.validate(artifact)
            guard_ms = (perf_counter() - guard_started) * 1000
            compile_success = True
            check_map = {item.guard: item.allowed for item in report.checks}
            values = self._filter_values(plan.get("filters", []))
            parameterized = all(value in artifact.params.values() and str(value) not in artifact.sql for value in values if value not in {0, None})
            actual = {
                "compile_success": True,
                "schema_valid": check_map.get("schema", False),
                "join_valid": not any(issue.code in {"UNVERIFIED_JOIN", "INVALID_JOIN_CONDITION", "DIRECT_FACT_JOIN"} for issue in report.issues),
                "parameterized_values": parameterized,
                "guard_allowed": report.allowed,
                "execution_success": "not_measured",
                "execution_equivalence": "not_measured",
                "sql": artifact.sql,
            }
            metrics = {key: float(value) for key, value in actual.items() if isinstance(value, bool)}
            passed = all(bool(actual.get(key)) == bool(case.expected.get(key, True)) for key in ("compile_success", "schema_valid", "join_valid", "parameterized_values", "guard_allowed"))
            return CaseOutcome(
                case_id=case.case_id, suite=self.suite, passed=passed,
                score=sum(metrics.values()) / len(metrics), metrics=metrics,
                expected=case.expected, actual=actual,
                latency_ms={"sql_generation": round(compile_ms, 3), "guardrail": round(guard_ms, 3)},
                failure_type=None if passed else "SQL_GENERATION_ERROR", stage="sql",
            )
        except Exception as exc:
            return CaseOutcome(
                case_id=case.case_id, suite=self.suite, passed=False, score=0,
                metrics={"compile_success": 0.0}, expected=case.expected,
                actual={"compile_success": compile_success, "error": type(exc).__name__, "message": str(exc)},
                latency_ms={"sql_generation": round((perf_counter() - started) * 1000, 3)},
                failure_type="SQL_GENERATION_ERROR", stage="sql_generation",
            )

    @classmethod
    def _filter_values(cls, nodes: list[dict[str, Any]]) -> list[Any]:
        values: list[Any] = []
        for node in nodes:
            if "logic" in node:
                values.extend(cls._filter_values(node.get("conditions", [])))
            elif isinstance(node.get("value"), list):
                values.extend(node["value"])
            else:
                values.append(node.get("value"))
        return values
