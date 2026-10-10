from __future__ import annotations

from typing import Any

from .models import CustomerFeature, CustomerTag
from .rule_evaluator import RuleEvaluator
from .rule_registry import RuleRegistry


class TagEngine:
    def __init__(self, registry: RuleRegistry | None = None):
        self.registry = registry or RuleRegistry()
        self.rules = self.registry.load("tag")
        self.evaluator = RuleEvaluator()

    def calculate(
        self,
        feature: CustomerFeature,
        user_parameters: dict[str, dict[str, Any]] | None = None,
        business_parameters: dict[str, dict[str, Any]] | None = None,
        include_unmatched: bool = False,
    ) -> list[CustomerTag]:
        output: list[CustomerTag] = []
        for tag_id, rule in self.rules.items():
            evaluation = self.evaluator.evaluate(
                feature, rule,
                (user_parameters or {}).get(tag_id),
                (business_parameters or {}).get(tag_id),
            )
            if not include_unmatched and evaluation.passed is not True:
                continue
            actual = next((item.actual_value for item in evaluation.evidence if item.passed is not None), None)
            threshold = next((item.threshold for item in evaluation.evidence if item.passed is not None), None)
            template = rule.get("explanation_template", "规则 {rule_id} 的条件已评估。")
            explanation = template.format(actual=actual, threshold=threshold, rule_id=tag_id)
            output.append(CustomerTag(
                tag_id=tag_id, name=rule["name"], customer_id=feature.customer_id,
                matched=evaluation.passed is True, status=evaluation.status,
                evidence=evaluation.evidence, parameters=evaluation.parameters,
                threshold_sources=evaluation.threshold_sources, rule_version=rule["version"],
                rule_source=rule["source"], time_range=feature.metric_time_range,
                explanation=explanation, warnings=evaluation.warnings,
            ))
        return output
