from __future__ import annotations

import json
from time import perf_counter

from agent.orchestrator import AgentOrchestrator
from benchmark.evaluators import (
    GuardrailEvaluator, HallucinationEvaluator, MarketingEvaluator, PlanEvaluator,
    ResultEvaluator, SQLEvaluator, SemanticEvaluator,
)
from benchmark.models import BenchmarkCase, CaseOutcome
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerator


class CaseRunner:
    def __init__(self):
        self.agent = AgentOrchestrator()
        self.evaluators = {
            "semantic": SemanticEvaluator(self.agent),
            "query_plan": PlanEvaluator(self.agent),
            "sql": SQLEvaluator(),
            "result": ResultEvaluator(),
            "hallucination": HallucinationEvaluator(),
            "guardrail": GuardrailEvaluator(),
            "marketing": MarketingEvaluator(),
        }
        self.generator = SQLGenerator()
        self.execution = ExecutionManager()

    def run(self, suite: str, case: BenchmarkCase) -> CaseOutcome:
        if suite in self.evaluators:
            return self.evaluators[suite].evaluate(case)
        if suite == "official_seed":
            outcome = self.evaluators["semantic"].evaluate(case)
            return outcome.model_copy(update={"suite": suite})
        if suite == "generalization":
            evaluator = self.evaluators["query_plan"] if "plan" in case.expected else self.evaluators["semantic"]
            outcome = evaluator.evaluate(case)
            return outcome.model_copy(update={"suite": suite})
        if suite == "multi_turn":
            return self._multi_turn(case)
        if suite == "end_to_end":
            return self._end_to_end(case)
        raise KeyError(f"unsupported suite: {suite}")

    def _multi_turn(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        context: dict = {}
        states = []
        normalized = []
        repeats = max(1, case.repeat)
        for _ in range(repeats):
            context = {}
            states = []
            for turn in case.turns or []:
                state = self.agent.run(turn, context)
                states.append(state)
                if state.query_plan:
                    context = {"previous_plan": state.query_plan, "parent_query_id": state.query_id}
            normalized.append(json.dumps(PlanEvaluator.normalize(states[-1].query_plan or {}), ensure_ascii=False, sort_keys=True))
        plan = states[-1].query_plan or {}
        expected = case.expected
        checks = {
            "metric_retention": set(expected.get("metrics", [])) <= set(plan.get("metrics", [])),
            "time_retention": plan.get("time_range") == expected.get("time_range"),
            "filter_patch": self._expected_filters(expected.get("filters", []), plan.get("filters", [])),
            "status": plan.get("status") == expected.get("status", "ready"),
            "output_stability": len(set(normalized)) == 1,
        }
        score = sum(checks.values()) / len(checks)
        return CaseOutcome(
            case_id=case.case_id, suite="multi_turn", passed=all(checks.values()), score=score,
            metrics={f"{key}_accuracy": float(value) for key, value in checks.items()},
            expected=expected, actual=PlanEvaluator.normalize(plan),
            latency_ms={"end_to_end": round((perf_counter() - started) * 1000, 3)},
            failure_type=None if all(checks.values()) else "CONTEXT_ERROR", stage="multi_turn",
            trace_id=states[-1].query_id if states else None,
        )

    @staticmethod
    def _expected_filters(expected, actual) -> bool:
        expected_set = {(item["type"], item["target"], item["operator"], json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True)) for item in expected}
        actual_set = {(item.get("type"), item.get("target"), item.get("operator"), json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True)) for item in actual if "logic" not in item}
        return expected_set <= actual_set

    def _end_to_end(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        state = self.agent.run(case.query or "")
        plan_ms = state.latency_ms or 0.0
        expected_status = case.expected.get("status", "ready")
        if expected_status != "ready":
            passed = state.status.value == expected_status
            return CaseOutcome(
                case_id=case.case_id, suite="end_to_end", passed=passed, score=float(passed),
                metrics={"end_to_end_success": float(passed), "result_accuracy": "not_measured", "hallucination": 0.0, "repair_count": state.repair_count, "clarification": float(state.clarification_needed), "trace_completeness": float(bool(state.trace and state.validation_result is not None))},
                expected=case.expected, actual={"status": state.status.value},
                latency_ms={"semantic_and_plan": plan_ms, "end_to_end": round((perf_counter() - started) * 1000, 3)},
                failure_type=None if passed else "CLARIFICATION_ERROR", stage="agent", trace_id=state.query_id,
            )
        try:
            generation_started = perf_counter()
            artifact = self.generator.generate(state.query_id, state.query_plan or {}, state.validation_result)
            generation_ms = (perf_counter() - generation_started) * 1000
            guard_started = perf_counter()
            dry_run = self.execution.dry_run(artifact)
            guard_ms = (perf_counter() - guard_started) * 1000
            passed = state.status.value == "ready" and dry_run.status == "validated"
            trace_checks = {
                "query_plan": bool(state.query_plan),
                "metric_source": bool(state.retrieved_metrics) or not (state.query_plan or {}).get("metrics"),
                "entity_resolution": state.resolved_entities is not None,
                "generated_sql": bool(artifact.sql),
                "guardrail_decisions": bool(dry_run.trace and dry_run.trace.validation.get("checks")),
            }
            return CaseOutcome(
                case_id=case.case_id, suite="end_to_end", passed=passed, score=float(passed),
                metrics={
                    "end_to_end_success": float(passed), "result_accuracy": "not_measured",
                    "hallucination": 0.0, "trace_completeness": sum(trace_checks.values()) / len(trace_checks),
                    "repair_count": state.repair_count, "clarification": float(state.clarification_needed),
                },
                expected=case.expected,
                actual={"status": state.status.value, "guardrail_status": dry_run.status, "trace_checks": trace_checks},
                latency_ms={"semantic_and_plan": plan_ms, "sql_generation": round(generation_ms, 3), "guardrail": round(guard_ms, 3), "db_execution": 0.0, "end_to_end": round((perf_counter() - started) * 1000, 3)},
                failure_type=None if passed else "VALIDATION_ERROR", stage="end_to_end", trace_id=state.query_id,
            )
        except Exception as exc:
            return CaseOutcome(
                case_id=case.case_id, suite="end_to_end", passed=False, score=0,
                metrics={"end_to_end_success": 0.0, "result_accuracy": "not_measured"},
                expected=case.expected, actual={"status": state.status.value, "error": type(exc).__name__, "message": str(exc)},
                latency_ms={"semantic_and_plan": plan_ms, "end_to_end": round((perf_counter() - started) * 1000, 3)},
                failure_type="SQL_GENERATION_ERROR", stage="end_to_end", trace_id=state.query_id,
            )
