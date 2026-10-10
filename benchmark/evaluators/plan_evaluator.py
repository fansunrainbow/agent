from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from agent.orchestrator import AgentOrchestrator
from agent.services.metadata_store import MetadataStore
from benchmark.metrics import set_scores
from benchmark.models import BenchmarkCase, CaseOutcome
from query_plan.canonicalizer import build_canonicalization_context

from .base import Evaluator
from .plan_equivalence import compare_plan_semantics


PLAN_FIELDS = ["intent", "metrics", "dimensions", "filters", "entities", "time_range", "group_by", "having", "order_by", "limit", "status"]


class PlanEvaluator(Evaluator):
    suite = "query_plan"

    def __init__(self, orchestrator: AgentOrchestrator | None = None):
        self.orchestrator = orchestrator or AgentOrchestrator()
        store = getattr(self.orchestrator, "store", None) or MetadataStore()
        self.canonicalization_context = build_canonicalization_context(
            store.yaml("metrics.yaml").get("metrics", {}),
            store.yaml("dimensions.yaml").get("dimensions", {}),
            store.yaml("business_dictionary.yaml").get("dictionary", {}),
        )

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        state = self.orchestrator.run(case.query or "")
        expected_raw = case.expected.get("plan", case.expected)
        actual_raw = state.query_plan or {}
        expected = self.normalize(expected_raw)
        actual = self.normalize(actual_raw)
        field_scores = {field: self._field_score(expected.get(field), actual.get(field)) for field in PLAN_FIELDS if field in expected}
        legacy_exact = bool(field_scores) and all(value == 1.0 for value in field_scores.values())
        raw_exact = expected_raw == actual_raw
        component_f1 = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
        comparison = compare_plan_semantics(expected_raw, actual_raw, self.canonicalization_context)
        canonical_exact = bool(comparison["equivalent"])
        actual["_comparison"] = comparison
        return CaseOutcome(
            case_id=case.case_id, suite=self.suite, passed=canonical_exact, score=component_f1,
            metrics={
                # Keep the Stage 8.0-8.2 normalized metric unchanged for longitudinal comparison.
                "plan_exact_match": float(legacy_exact),
                "legacy_normalized_plan_exact_match": float(legacy_exact),
                # Stage 8.3 adds the requested strict structural/raw comparison.
                "raw_plan_exact_match": float(raw_exact),
                "canonical_plan_exact_match": float(canonical_exact),
                "plan_component_f1": component_f1,
                "repair_count": state.repair_count,
                "clarification": float(state.clarification_needed),
                **{f"component_{key}": value for key, value in field_scores.items()},
            },
            expected=expected, actual=actual,
            latency_ms={"query_plan": round((perf_counter() - started) * 1000, 3)},
            failure_type=None if canonical_exact else "PLAN_ERROR", stage="query_plan", trace_id=state.query_id,
        )

    @classmethod
    def normalize(cls, plan: dict[str, Any]) -> dict[str, Any]:
        output = {key: plan.get(key) for key in PLAN_FIELDS if key in plan}
        for key in ("metrics", "dimensions", "group_by"):
            if key in output:
                output[key] = sorted(output[key] or [])
        for key in ("filters", "having"):
            if key in output:
                output[key] = sorted((cls._normalize_filter(item) for item in output[key] or []), key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        if "entities" in output:
            output["entities"] = sorted((cls._normalize_entity(item) for item in output["entities"] or []), key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        if "order_by" in output:
            # ORDER BY is ordered business semantics; never sort it for comparison.
            output["order_by"] = list(output["order_by"] or [])
        return output

    @classmethod
    def _normalize_filter(cls, node: dict[str, Any]) -> dict[str, Any]:
        if "logic" in node:
            children = [cls._normalize_filter(item) for item in node.get("conditions", [])]
            if node["logic"] in {"and", "or"}:
                children.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
            return {"logic": node["logic"], "conditions": children}
        return {key: node.get(key) for key in ("type", "target", "operator", "value")}

    @staticmethod
    def _normalize_entity(entity: dict[str, Any]) -> dict[str, Any]:
        resolved = entity.get("resolved") or {}
        return {"entity_type": entity.get("entity_type"), "resolution_status": entity.get("resolution_status"), "id": resolved.get("id")}

    @staticmethod
    def _field_score(expected: Any, actual: Any) -> float:
        if isinstance(expected, list) and isinstance(actual, list):
            return float(set_scores((json.dumps(item, ensure_ascii=False, sort_keys=True) for item in expected), (json.dumps(item, ensure_ascii=False, sort_keys=True) for item in actual))["f1"])
        return float(expected == actual)
