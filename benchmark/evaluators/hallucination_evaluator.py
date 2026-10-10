from __future__ import annotations

from time import perf_counter

from agent.orchestrator import AgentOrchestrator
from benchmark.models import BenchmarkCase, CaseOutcome
from guardrail.catalog import MetadataCatalog
from guardrail.sql_validator import SQLValidator
from marketing.services import CustomerProfileService
from marketing.strategy_engine import StrategyEngine

from .base import Evaluator
from .marketing_evaluator import MarketingEvaluator


class HallucinationEvaluator(Evaluator):
    suite = "hallucination"

    def __init__(self):
        self.agent = AgentOrchestrator()
        self.catalog = MetadataCatalog()
        self.sql = SQLValidator()
        self.marketing = MarketingEvaluator()

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        mode = case.input.get("mode", "agent")
        expected_action = case.expected.get("action", "reject")
        hallucinated = False
        handled = False
        actual = {}
        trace_id = None
        stage = mode
        if mode == "agent":
            state = self.agent.run(case.query or "")
            plan = state.query_plan or {}
            metrics = set(plan.get("metrics", []))
            dimensions = set(plan.get("dimensions", []))
            concepts = {item.get("target") for item in self._filters(plan.get("filters", [])) if item.get("type") == "concept"}
            hallucinated = bool(metrics - set(self.catalog.metrics) or dimensions - set(self.catalog.dimensions) or concepts - set(self.catalog.dictionary))
            handled = state.status.value in {"unsupported", "needs_clarification"} if expected_action == "reject" else state.status.value == "ready"
            actual = {"status": state.status.value, "metrics": sorted(metrics), "dimensions": sorted(dimensions), "concepts": sorted(concepts), "hallucinated": hallucinated}
            trace_id = state.query_id
        elif mode == "guardrail":
            report = self.sql.validate(case.input["sql"])
            handled = not report.allowed
            hallucinated = report.allowed
            actual = {"allowed": report.allowed, "issues": [item.code for item in report.issues]}
        else:
            marketing_case = case.model_copy(update={"category": "marketing", "input": {key: value for key, value in case.input.items() if key != "mode"}})
            outcome = self.marketing.evaluate(marketing_case)
            handled = outcome.passed
            hallucinated = not outcome.passed
            actual = outcome.actual
        passed = handled and not hallucinated
        return CaseOutcome(
            case_id=case.case_id, suite=self.suite, passed=passed, score=float(passed),
            metrics={
                "hallucinated": float(hallucinated),
                "unsupported_handling_accuracy": float(handled),
                "semantic_hallucination": float(hallucinated and mode == "agent"),
                "sql_hallucination": float(hallucinated and mode == "guardrail"),
                "marketing_hallucination": float(hallucinated and mode not in {"agent", "guardrail"}),
            },
            expected=case.expected, actual=actual,
            latency_ms={"hallucination_case": round((perf_counter() - started) * 1000, 3)},
            failure_type=None if passed else "UNSUPPORTED_HANDLING_ERROR", stage=stage, trace_id=trace_id,
        )

    @classmethod
    def _filters(cls, nodes):
        for node in nodes:
            if "logic" in node:
                yield from cls._filters(node.get("conditions", []))
            else:
                yield node
