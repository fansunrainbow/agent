from __future__ import annotations

from marketing.explanation import ExplanationLayer
from marketing.opportunity_detector import OpportunityDetector
from marketing.segment_engine import SegmentEngine
from marketing.services import CohortAnalysisService, CustomerProfileService, MarketingAnalysisService
from marketing.strategy_engine import StrategyEngine
from marketing.tag_engine import TagEngine


def test_customer_360_has_required_profiles_and_explainable_tags(customer_factory):
    customer = customer_factory()
    tags = TagEngine().calculate(customer)
    profile = CustomerProfileService().build_360(customer, tags)
    for key in ("basic_profile", "asset_profile", "holding_profile", "trading_profile", "fund_flow_profile", "allocation_profile", "tags"):
        assert key in profile
    fund_tag = next(item for item in profile["tags"] if item["tag_id"] == "fund_low_allocation")
    assert fund_tag["evidence"][0]["actual_value"] == 0.043


def test_cohort_analysis_uses_only_usable_registered_features(customer_factory):
    customers = [customer_factory("c1"), customer_factory("c2", {"average_total_asset": 1_000_000, "period_end_asset": 1_100_000, "city": "苏州"})]
    segment = SegmentEngine().evaluate("fund_low_allocation", customers)
    analysis = CohortAnalysisService().analyze(segment, customers)
    assert analysis["customer_count"] == 2
    assert analysis["asset_scale"] == 3_000_000
    assert analysis["distributions"]["city"] == {"南京": 1, "苏州": 1}


def test_opportunity_evidence_and_strategy_fact_rule_suggestion_are_separate(customer_factory):
    customer = customer_factory()
    opportunities = OpportunityDetector().find(customer)
    fund = next(item for item in opportunities if item.opportunity_id == "fund_allocation_opportunity")
    assert fund.actual_values == {"average_total_asset": 1_850_000, "fund_holding_ratio": 0.043}
    strategies = StrategyEngine().get_strategies(customer, opportunities)
    strategy = next(item for item in strategies if item.strategy_id == "improve_fund_allocation")
    assert all(item["type"] == "FACT" for item in strategy.facts)
    assert all(item["type"] == "RULE_DECISION" for item in strategy.rule_decisions)
    assert all(item["type"] == "SUGGESTION" for item in strategy.suggestions)


def test_explanation_contains_rule_provenance_and_condition_evidence(customer_factory):
    opportunity = OpportunityDetector().find(customer_factory())[0]
    explanation = ExplanationLayer().explain(opportunity)
    assert explanation["decision_type"] == "opportunity"
    assert explanation["rule_version"] == "1.0"
    assert explanation["rule_source"]
    assert all({"feature_id", "actual_value", "operator", "threshold", "passed", "source", "time_range"} <= set(item) for item in explanation["evidence"])


def test_marketing_trace_is_complete(customer_factory):
    result = MarketingAnalysisService().analyze_customer(customer_factory())
    trace = result["trace"]
    assert trace["customer_id"] == "c1"
    assert trace["features"] and trace["tags"] and trace["opportunities"] and trace["strategies"]
    assert trace["time_range"]


def test_specific_product_recommendation_is_refused_without_suitability():
    result = StrategyEngine().request_specific_product_recommendation("某具体基金")
    assert result["allowed"] is False
    assert result["code"] == "SUITABILITY_DATA_REQUIRED"
