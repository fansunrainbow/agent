from __future__ import annotations

from time import perf_counter
from typing import Any

from benchmark.metrics import set_scores
from benchmark.models import BenchmarkCase, CaseOutcome
from marketing.explanation import ExplanationLayer
from marketing.models import CustomerFeature, FeatureValue
from marketing.opportunity_detector import OpportunityDetector
from marketing.segment_engine import SegmentEngine
from marketing.services import CustomerProfileService
from marketing.strategy_engine import StrategyEngine
from marketing.tag_engine import TagEngine

from .base import Evaluator


class MarketingEvaluator(Evaluator):
    suite = "marketing"

    def __init__(self):
        self.tags = TagEngine()
        self.segments = SegmentEngine()
        self.opportunities = OpportunityDetector()
        self.strategies = StrategyEngine()
        self.profiles = CustomerProfileService()
        self.explanations = ExplanationLayer()

    def evaluate(self, case: BenchmarkCase) -> CaseOutcome:
        started = perf_counter()
        feature = self._feature(case.input)
        target = case.input["target"]
        expected = case.expected
        actual: dict[str, Any] = {}
        metrics: dict[str, float] = {}
        if target == "tags":
            ids = [item.tag_id for item in self.tags.calculate(feature)]
            actual["ids"] = ids
            metrics["tag_f1"] = float(set_scores(expected["ids"], ids)["f1"])
        elif target == "segment":
            result = self.segments.evaluate(case.input["rule_id"], [feature], user_parameters=case.input.get("parameters"))
            actual = {"matched": bool(result.matched_customer_ids), "excluded_due_to_missing": bool(result.excluded_due_to_missing), "warnings": result.warnings}
            metrics["segment_accuracy"] = float(actual["matched"] == expected.get("matched"))
            if "excluded_due_to_missing" in expected:
                metrics["missing_exclusion_accuracy"] = float(actual["excluded_due_to_missing"] == expected["excluded_due_to_missing"])
            if "time_conflict" in expected:
                metrics["time_conflict_detection_accuracy"] = float(any(item.get("code") == "METRIC_TIME_RANGE_CONFLICT" for item in result.warnings) == expected["time_conflict"])
        elif target in {"opportunities", "strategies", "explanation"}:
            opportunities = self.opportunities.find(feature)
            if target == "opportunities":
                ids = [item.opportunity_id for item in opportunities]
                actual["ids"] = ids
                metrics["opportunity_f1"] = float(set_scores(expected["ids"], ids)["f1"])
                metrics["evidence_completeness"] = float(all(item.matched_rules and item.actual_values and item.thresholds and item.rule_version and item.rule_source for item in opportunities))
            elif target == "strategies":
                strategies = self.strategies.get_strategies(feature, opportunities)
                ids = [item.strategy_id for item in strategies]
                actual["ids"] = ids
                metrics["strategy_rule_f1"] = float(set_scores(expected["ids"], ids)["f1"])
                metrics["fact_rule_suggestion_separation"] = float(all(item.facts and item.rule_decisions and item.suggestions for item in strategies))
            else:
                decision = next(item for item in opportunities if item.opportunity_id == case.input["rule_id"])
                explanation = self.explanations.explain(decision)
                required = set(expected["required_fields"])
                actual["fields"] = sorted(explanation)
                actual["evidence_fields"] = sorted(set.intersection(*(set(item) for item in explanation["evidence"]))) if explanation["evidence"] else []
                metrics["explanation_completeness"] = float(required <= set(explanation) and set(expected.get("required_evidence_fields", [])) <= set(actual["evidence_fields"]))
        elif target == "attribute":
            actual = self.profiles.get_attribute(feature, case.input["attribute_id"])
            metrics["unsupported_handling_accuracy"] = float(actual.get("supported") == expected["supported"] and actual.get("code") == expected.get("code"))
        elif target == "specific_product":
            actual = self.strategies.request_specific_product_recommendation(case.input["product_name"])
            metrics["suitability_guard_accuracy"] = float(actual.get("allowed") == expected["allowed"] and actual.get("code") == expected.get("code"))
        else:
            raise ValueError(f"unknown marketing target: {target}")
        score = sum(metrics.values()) / len(metrics) if metrics else 0.0
        passed = score == 1.0
        return CaseOutcome(
            case_id=case.case_id, suite=self.suite, passed=passed, score=score,
            metrics=metrics, expected=expected, actual=actual,
            latency_ms={"marketing": round((perf_counter() - started) * 1000, 3)},
            failure_type=None if passed else "MARKETING_RULE_ERROR", stage="marketing",
        )

    @staticmethod
    def _feature(data: dict[str, Any]) -> CustomerFeature:
        time_range = data.get("time_range", {"type": "quarter", "year": 2026, "quarter": 1})
        dimensions = {"age", "gender", "customer_level", "city", "branch", "province"}
        states = data.get("missing_states", {})
        ranges = data.get("feature_time_ranges", {})
        values: dict[str, FeatureValue] = {}
        for feature_id, value in data.get("features", {}).items():
            kind = "dimension" if feature_id in dimensions else "metric"
            state = states.get(feature_id, "zero" if kind == "metric" and value == 0 else ("no_record" if kind == "metric" and value is None else ("unknown" if value is None else "observed")))
            values[feature_id] = FeatureValue(feature_id, kind, value, ranges.get(feature_id, time_range if kind == "metric" else None), "human_reviewed_fixture", 1.0, state)
        return CustomerFeature(
            customer_id=str(data.get("customer_id", "MASKED-CUSTOMER")), features=values,
            source_metrics=[key for key, item in values.items() if item.kind == "metric"],
            source_dimensions=[key for key, item in values.items() if item.kind == "dimension"],
            attribute_snapshot_date=data.get("attribute_snapshot_date", "20260531"),
            metric_time_range=time_range, confidence=1.0,
        )
