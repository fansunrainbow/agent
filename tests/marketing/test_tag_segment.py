from __future__ import annotations

from marketing.segment_engine import SegmentEngine
from marketing.tag_engine import TagEngine


def test_tag_is_evidence_backed_and_threshold_is_parameterized(customer_factory):
    customer = customer_factory()
    tags = TagEngine().calculate(customer, user_parameters={"high_asset": {"threshold": 2_000_000}}, include_unmatched=True)
    high_asset = next(item for item in tags if item.tag_id == "high_asset")
    assert not high_asset.matched
    assert high_asset.threshold_sources["threshold"] == "user_input"
    assert high_asset.evidence[0].actual_value == 1_850_000
    assert high_asset.evidence[0].threshold == 2_000_000


def test_business_threshold_overrides_default(customer_factory):
    tags = TagEngine().calculate(
        customer_factory(), business_parameters={"fund_low_allocation": {"threshold": 0.04}}, include_unmatched=True,
    )
    tag = next(item for item in tags if item.tag_id == "fund_low_allocation")
    assert not tag.matched
    assert tag.threshold_sources["threshold"] == "business_config"


def test_segment_supports_and_or_not(customer_factory):
    customers = [
        customer_factory("c1"),
        customer_factory("c2", {"average_total_asset": 500_000, "fund_holding_ratio": 0.2, "trade_count": 10, "net_inflow": 10, "asset_change_rate": 0.1}),
        customer_factory("c3", {"average_total_asset": 500_000, "fund_holding_ratio": 0.2, "trade_count": 30, "net_inflow": 100}),
    ]
    engine = SegmentEngine()
    assert engine.evaluate("high_asset_low_fund", customers).matched_customer_ids == ["c1"]
    assert set(engine.evaluate("positive_flow_or_growth", customers).matched_customer_ids) == {"c2", "c3"}
    assert engine.evaluate("active_non_outflow", customers).matched_customer_ids == ["c3"]


def test_missing_is_not_zero_and_not_does_not_invert_unknown(customer_factory):
    customer = customer_factory("c1", {"net_inflow": None}, {"net_inflow": "no_record"})
    result = SegmentEngine().evaluate("active_non_outflow", [customer])
    assert result.matched_customer_ids == []
    assert result.excluded_due_to_missing == ["c1"]


def test_time_range_conflict_is_rejected(customer_factory, time_range):
    different = {"type": "month", "year": 2026, "month": 4}
    customer = customer_factory(ranges={"fund_holding_ratio": different})
    result = SegmentEngine().evaluate("high_asset_low_fund", [customer])
    assert result.matched_customer_ids == []
    assert result.excluded_due_to_missing == ["c1"]
    assert any(item["code"] == "METRIC_TIME_RANGE_CONFLICT" for item in result.warnings)
