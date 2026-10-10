from __future__ import annotations

from typing import Any

from .models import CustomerFeature, SegmentResult
from .rule_evaluator import RuleEvaluator
from .rule_registry import RuleRegistry


class SegmentEngine:
    def __init__(self, registry: RuleRegistry | None = None):
        self.registry = registry or RuleRegistry()
        self.rules = self.registry.load("segment")
        self.evaluator = RuleEvaluator()

    def evaluate(
        self,
        segment_id: str,
        features: list[CustomerFeature],
        user_parameters: dict[str, Any] | None = None,
        business_parameters: dict[str, Any] | None = None,
    ) -> SegmentResult:
        if segment_id not in self.rules:
            raise KeyError(f"unknown segment rule: {segment_id}")
        rule = self.rules[segment_id]
        matched: list[str] = []
        excluded: list[str] = []
        evidence: dict[str, list[dict[str, Any]]] = {}
        warnings: list[dict[str, Any]] = []
        threshold_sources: dict[str, str] = {}
        time_range = None
        for feature in features:
            evaluation = self.evaluator.evaluate(feature, rule, user_parameters, business_parameters)
            threshold_sources = evaluation.threshold_sources
            if evaluation.passed is True:
                matched.append(feature.customer_id)
                evidence[feature.customer_id] = [item.to_dict() for item in evaluation.evidence]
            elif evaluation.passed is None:
                excluded.append(feature.customer_id)
            warnings.extend({**item, "customer_id": feature.customer_id} for item in evaluation.warnings)
            time_range = time_range or feature.metric_time_range
        return SegmentResult(
            segment_id=segment_id, name=rule["name"], matched_customer_ids=matched,
            customer_count=len(matched), rule=rule["condition"], threshold_sources=threshold_sources,
            time_range=time_range, evidence=evidence, rule_version=rule["version"],
            rule_source=rule["source"], excluded_due_to_missing=excluded, warnings=warnings,
        )
