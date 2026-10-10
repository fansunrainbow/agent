from __future__ import annotations

from typing import Any

from .models import CustomerFeature, Opportunity
from .rule_evaluator import RuleEvaluator
from .rule_registry import RuleRegistry


class OpportunityDetector:
    def __init__(self, registry: RuleRegistry | None = None):
        self.registry = registry or RuleRegistry()
        self.rules = self.registry.load("opportunity")
        self.evaluator = RuleEvaluator()

    def find(
        self,
        feature: CustomerFeature,
        user_parameters: dict[str, dict[str, Any]] | None = None,
        business_parameters: dict[str, dict[str, Any]] | None = None,
    ) -> list[Opportunity]:
        output: list[Opportunity] = []
        for opportunity_id, rule in self.rules.items():
            evaluation = self.evaluator.evaluate(
                feature, rule,
                (user_parameters or {}).get(opportunity_id),
                (business_parameters or {}).get(opportunity_id),
            )
            if evaluation.passed is not True:
                continue
            wanted = set(rule.get("evidence", []))
            actual = {item.feature_id: item.actual_value for item in evaluation.evidence if item.feature_id in wanted}
            thresholds = {item.feature_id: item.threshold for item in evaluation.evidence if item.feature_id in wanted}
            output.append(Opportunity(
                opportunity_id=opportunity_id, name=rule["name"], customer_id=feature.customer_id,
                priority=rule.get("priority", "medium"),
                matched_rules=[item.to_dict() for item in evaluation.evidence],
                actual_values=actual, thresholds=thresholds,
                threshold_sources=evaluation.threshold_sources,
                time_range=feature.metric_time_range, rule_version=rule["version"],
                rule_source=rule["source"], explanation=rule.get("explanation_template", ""),
            ))
        return output
