from __future__ import annotations

from time import perf_counter
from typing import Any

from agent.orchestrator import AgentOrchestrator
from benchmark.metrics import set_scores
from benchmark.models import BenchmarkCase, CaseOutcome

from .base import Evaluator


class SemanticEvaluator(Evaluator):
    suite = "semantic"

    def __init__(self, orchestrator: AgentOrchestrator | None = None):
        self.orchestrator = orchestrator or AgentOrchestrator()

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        state = self.orchestrator.run(case.query or "")
        plan = state.query_plan or {}
        expected = case.expected
        actual = {
            "intent": plan.get("intent"),
            "status": plan.get("status") or state.status.value,
            "metrics": plan.get("metrics", []),
            "dimensions": plan.get("dimensions", []),
            "concepts": sorted({item.target for item in state.grounded_conditions if item.semantic_type == "concept" and item.target}),
            "operators": sorted({item.get("operator") for item in self._filters(plan.get("filters", [])) if item.get("operator")}),
            "time_range": plan.get("time_range"),
            "entities": sorted(str(item.get("resolved", {}).get("id")) for item in plan.get("entities", []) if item.get("resolved")),
            "clarification": state.clarification_needed,
            "unsupported": state.status.value == "unsupported",
        }
        scores: dict[str, float] = {}
        for key in ("metrics", "dimensions", "concepts", "operators", "entities"):
            if key in expected:
                set_metric = set_scores(expected[key], actual[key])
                scores[f"{key}_precision"] = float(set_metric["precision"])
                scores[f"{key}_recall"] = float(set_metric["recall"])
                scores[f"{key}_f1"] = float(set_metric["f1"])
        for key in ("intent", "status", "time_range", "clarification", "unsupported"):
            if key in expected:
                scores[f"{key}_accuracy"] = float(actual[key] == expected[key])
        score = sum(scores.values()) / len(scores) if scores else 0.0
        scores["repair_count"] = state.repair_count
        scores["clarification"] = float(state.clarification_needed)
        passed = score == 1.0
        failure = None if passed else self._failure(expected, actual)
        return CaseOutcome(
            case_id=case.case_id, suite=self.suite, passed=passed, score=score,
            metrics=scores, expected=expected, actual=actual,
            latency_ms={"semantic_and_plan": round((perf_counter() - started) * 1000, 3)},
            failure_type=failure, stage="semantic", trace_id=state.query_id,
        )

    @classmethod
    def _filters(cls, nodes: list[dict[str, Any]]):
        for node in nodes:
            if "logic" in node:
                yield from cls._filters(node.get("conditions", []))
            else:
                yield node

    @staticmethod
    def _failure(expected: dict[str, Any], actual: dict[str, Any]) -> str:
        if expected.get("unsupported") and not actual.get("unsupported"):
            return "UNSUPPORTED_HANDLING_ERROR"
        if expected.get("clarification") and not actual.get("clarification"):
            return "CLARIFICATION_ERROR"
        if "time_range" in expected and expected.get("time_range") != actual.get("time_range"):
            return "TIME_PARSE_ERROR"
        if expected.get("entities") != actual.get("entities") and "entities" in expected:
            return "ENTITY_RESOLUTION_ERROR"
        return "SEMANTIC_ERROR"
