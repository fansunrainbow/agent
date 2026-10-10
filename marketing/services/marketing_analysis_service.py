from __future__ import annotations

from typing import Any

from ..explanation import ExplanationLayer
from ..models import CustomerFeature
from ..opportunity_detector import OpportunityDetector
from ..strategy_engine import StrategyEngine
from ..tag_engine import TagEngine
from .customer_profile_service import CustomerProfileService


class MarketingAnalysisService:
    def __init__(self):
        self.tags = TagEngine()
        self.opportunities = OpportunityDetector()
        self.strategies = StrategyEngine()
        self.profiles = CustomerProfileService()
        self.explanations = ExplanationLayer()

    def analyze_customer(
        self,
        feature: CustomerFeature,
        *,
        tag_parameters: dict[str, dict[str, Any]] | None = None,
        opportunity_parameters: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        tags = self.tags.calculate(feature, user_parameters=tag_parameters)
        opportunities = self.opportunities.find(feature, user_parameters=opportunity_parameters)
        strategies = self.strategies.get_strategies(feature, opportunities)
        return {
            "customer_id": feature.customer_id,
            "customer_360": self.profiles.build_360(feature, tags),
            "tags": [item.to_dict() for item in tags],
            "opportunities": [item.to_dict() for item in opportunities],
            "strategies": [item.to_dict() for item in strategies],
            "explanations": [self.explanations.explain(item) for item in [*tags, *opportunities, *strategies]],
            "trace": {
                "customer_id": feature.customer_id,
                "features": {key: value.to_dict() for key, value in feature.features.items()},
                "tags": [{"rule_id": item.tag_id, "rule_version": item.rule_version, "threshold_source": item.threshold_sources} for item in tags],
                "opportunities": [{"rule_id": item.opportunity_id, "rule_version": item.rule_version, "threshold_source": item.threshold_sources} for item in opportunities],
                "strategies": [{"rule_id": item.strategy_id, "rule_version": item.rule_version} for item in strategies],
                "time_range": feature.metric_time_range,
            },
        }
