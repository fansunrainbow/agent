from __future__ import annotations

from typing import Any

import yaml

from .models import CustomerFeature, Opportunity, StrategyResult
from .rule_registry import RULE_DIR, RuleRegistry


class StrategyEngine:
    def __init__(self, registry: RuleRegistry | None = None):
        self.registry = registry or RuleRegistry()
        self.rules = self.registry.load("strategy")
        with (self.registry.rule_dir / "strategy_rules.yaml").open("r", encoding="utf-8") as handle:
            self.policy = (yaml.safe_load(handle) or {}).get("policy", {})

    def get_strategies(self, feature: CustomerFeature, opportunities: list[Opportunity]) -> list[StrategyResult]:
        by_id = {item.opportunity_id: item for item in opportunities}
        output: list[StrategyResult] = []
        for strategy_id, rule in self.rules.items():
            triggers = [by_id[item] for item in rule.get("trigger_opportunities", []) if item in by_id]
            if not triggers:
                continue
            facts = []
            decisions = []
            for opportunity in triggers:
                for feature_id, value in opportunity.actual_values.items():
                    facts.append({"type": "FACT", "feature_id": feature_id, "value": value, "source": "stage6_safe_result", "time_range": opportunity.time_range})
                decisions.append({
                    "type": "RULE_DECISION", "opportunity_id": opportunity.opportunity_id,
                    "rule_version": opportunity.rule_version, "matched": True,
                })
            output.append(StrategyResult(
                customer_id=feature.customer_id, strategy_id=strategy_id, name=rule["name"],
                facts=facts, rule_decisions=decisions,
                suggestions=[{
                    "type": "SUGGESTION",
                    "action_type": rule["action"].get("type"),
                    "description": rule["action"].get("description"),
                }],
                prohibited_actions=rule.get("prohibited", []), rule_version=rule["version"],
                rule_source=rule["source"], time_range=feature.metric_time_range,
            ))
        return output

    def request_specific_product_recommendation(self, product_name: str) -> dict[str, Any]:
        if not self.policy.get("suitability_data_available") or not self.policy.get("allow_specific_product_recommendation"):
            return {
                "allowed": False,
                "code": "SUITABILITY_DATA_REQUIRED",
                "message": "当前缺少客户适当性、产品风险等级和合规匹配依据，不能推荐具体金融产品。",
                "requested_product": product_name,
                "safe_alternative": "仅可提供产品类别层面的经营沟通建议。",
            }
        return {"allowed": True}
