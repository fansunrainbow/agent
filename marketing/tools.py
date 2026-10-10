from __future__ import annotations

from typing import Any

from guardrail.execution_manager import ExecutionResult
from guardrail.models import SQLArtifact

from .explanation import ExplanationLayer
from .feature_builder import CustomerFeatureBuilder
from .models import CustomerFeature, Opportunity, SegmentResult
from .opportunity_detector import OpportunityDetector
from .segment_engine import SegmentEngine
from .services import CohortAnalysisService, CustomerProfileService, MarketingAnalysisService
from .strategy_engine import StrategyEngine
from .tag_engine import TagEngine


class MarketingTools:
    """Stable tool-style facade for Agent integration; engines remain deterministic."""

    def __init__(self):
        self.feature_builder = CustomerFeatureBuilder()
        self.tag_engine = TagEngine()
        self.segment_engine = SegmentEngine()
        self.opportunity_detector = OpportunityDetector()
        self.strategy_engine = StrategyEngine()
        self.profile_service = CustomerProfileService()
        self.cohort_service = CohortAnalysisService()
        self.analysis_service = MarketingAnalysisService()
        self.explanation = ExplanationLayer()

    def build_customer_profile(self, result: ExecutionResult, artifact: SQLArtifact) -> list[CustomerFeature]:
        return self.feature_builder.build(result, artifact)

    def calculate_tags(self, feature: CustomerFeature, **kwargs):
        return self.tag_engine.calculate(feature, **kwargs)

    def evaluate_segment(self, segment_id: str, features: list[CustomerFeature], **kwargs) -> SegmentResult:
        return self.segment_engine.evaluate(segment_id, features, **kwargs)

    def analyze_segment(self, segment: SegmentResult, features: list[CustomerFeature]) -> dict[str, Any]:
        return self.cohort_service.analyze(segment, features)

    def find_opportunities(self, feature: CustomerFeature, **kwargs) -> list[Opportunity]:
        return self.opportunity_detector.find(feature, **kwargs)

    def get_strategy(self, feature: CustomerFeature, opportunities: list[Opportunity]):
        return self.strategy_engine.get_strategies(feature, opportunities)

    def explain_marketing_decision(self, decision: Any) -> dict[str, Any]:
        return self.explanation.explain(decision)
