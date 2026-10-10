from __future__ import annotations

import pytest

from agent.services.metadata_store import MetadataStore
from benchmark.evaluators.plan_equivalence import compare_plan_semantics
from query_plan.canonicalizer import build_canonicalization_context, canonicalize_query_plan


@pytest.fixture(scope="module")
def context():
    store = MetadataStore()
    return build_canonicalization_context(
        store.yaml("metrics.yaml").get("metrics", {}),
        store.yaml("dimensions.yaml").get("dimensions", {}),
        store.yaml("business_dictionary.yaml").get("dictionary", {}),
    )


def equivalent(expected, actual, context) -> bool:
    return compare_plan_semantics(expected, actual, context)["equivalent"]


def leaf(target: str, value, operator: str = "eq", kind: str = "dimension"):
    return {"type": kind, "target": target, "operator": operator, "value": value}


def test_null_and_empty_list_are_equivalent_for_list_fields(context):
    assert equivalent({"metrics": None}, {"metrics": []}, context)


def test_metric_list_order_is_not_semantic(context):
    assert equivalent(
        {"metrics": ["average_total_asset", "stock_trade_amount"]},
        {"metrics": ["stock_trade_amount", "average_total_asset"]}, context,
    )


def test_dimension_list_order_is_not_semantic(context):
    assert equivalent({"dimensions": ["city", "gender"]}, {"dimensions": ["gender", "city"]}, context)


def test_entity_list_order_is_not_semantic(context):
    a = {"entity_type": "product", "resolution_status": "resolved", "resolved": {"id": "P1", "name": "甲"}}
    b = {"entity_type": "product", "resolution_status": "resolved", "resolved": {"id": "P2", "name": "乙"}}
    assert equivalent({"entities": [a, b]}, {"entities": [b, a]}, context)


def test_and_child_order_is_not_semantic(context):
    a, b = leaf("city", "南京"), leaf("gender", "男")
    assert equivalent({"filters": [{"logic": "and", "conditions": [a, b]}]}, {"filters": [{"logic": "and", "conditions": [b, a]}]}, context)


def test_or_child_order_is_not_semantic(context):
    a, b = leaf("city", "南京"), leaf("city", "苏州")
    assert equivalent({"filters": [{"logic": "or", "conditions": [a, b]}]}, {"filters": [{"logic": "or", "conditions": [b, a]}]}, context)


def test_nested_and_is_flattened(context):
    a, b, c = leaf("city", "南京"), leaf("gender", "男"), leaf("customer_level", "1000001")
    nested = {"logic": "and", "conditions": [a, {"logic": "and", "conditions": [b, c]}]}
    flat = {"logic": "and", "conditions": [c, a, b]}
    assert equivalent({"filters": [nested]}, {"filters": [flat]}, context)


def test_nested_or_is_flattened(context):
    a, b, c = leaf("city", "南京"), leaf("city", "苏州"), leaf("city", "无锡")
    nested = {"logic": "or", "conditions": [a, {"logic": "or", "conditions": [b, c]}]}
    flat = {"logic": "or", "conditions": [c, a, b]}
    assert equivalent({"filters": [nested]}, {"filters": [flat]}, context)


def test_not_structure_is_preserved(context):
    positive = {"filters": [leaf("customer_status", "2000005")]}
    negative = {"filters": [{"logic": "not", "conditions": [leaf("customer_status", "2000005")]}]}
    assert not equivalent(positive, negative, context)


def test_operator_aliases_are_canonicalized(context):
    assert equivalent({"filters": [leaf("age", 30, ">=")]}, {"filters": [leaf("age", 30.0, "gte")]}, context)


def test_membership_value_order_is_not_semantic(context):
    assert equivalent(
        {"filters": [leaf("city", ["南京", "苏州"], "in")]},
        {"filters": [leaf("city", ["苏州", "南京"], "in")]}, context,
    )


def test_between_bound_order_is_semantic(context):
    assert not equivalent(
        {"filters": [leaf("age", [10, 20], "between")]},
        {"filters": [leaf("age", [20, 10], "between")]}, context,
    )


def test_percentage_is_normalized_only_for_ratio_metric(context):
    assert equivalent(
        {"filters": [leaf("fund_holding_ratio", "10%", "lt", "metric")]},
        {"filters": [leaf("fund_holding_ratio", 0.1, "<", "metric")]}, context,
    )
    assert canonicalize_query_plan({"filters": [leaf("age", "10%", "eq")]}, context)["filters"]["value"] == "10%"


def test_quarter_and_proven_equivalent_date_range_match(context):
    assert equivalent(
        {"time_range": {"type": "quarter", "year": 2026, "quarter": 1, "raw_expression": "2026年Q1"}},
        {"time_range": {"type": "date_range", "start": "2026-01-01", "end": "2026-03-31"}}, context,
    )


def test_entity_aliases_with_same_canonical_id_match(context):
    expected = {"entities": [{"entity_type": "city", "surface": "南京", "resolution_status": "resolved", "resolved": {"id": "320100", "name": "南京市"}}]}
    actual = {"entities": [{"entity_type": "city", "surface": "南京市", "resolution_status": "resolved", "resolved": {"id": "320100", "name": "南京"}}]}
    result = compare_plan_semantics(expected, actual, context)
    assert result["equivalent"]
    assert any(item["path"] == "entities" for item in result["ignored_differences"])


def test_confidence_is_explicitly_ignored(context):
    result = compare_plan_semantics({"metrics": ["customer_count"], "confidence": 0.4}, {"metrics": ["customer_count"], "confidence": 0.99}, context)
    assert result["equivalent"]
    assert {item["path"] for item in result["ignored_differences"]} == {"confidence"}


def test_ready_and_needs_clarification_are_not_equal(context):
    assert not equivalent({"status": "ready"}, {"status": "needs_clarification"}, context)


def test_different_metrics_are_not_equal(context):
    assert not equivalent({"metrics": ["customer_count"]}, {"metrics": ["average_total_asset"]}, context)


def test_different_intents_are_not_equal(context):
    assert not equivalent({"intent": "metric_query"}, {"intent": "group_analysis"}, context)


def test_different_filter_values_are_not_equal(context):
    assert not equivalent({"filters": [leaf("city", "南京")]}, {"filters": [leaf("city", "苏州")]}, context)


def test_ambiguous_and_resolved_entities_are_not_equal(context):
    ambiguous = {"entities": [{"entity_type": "product", "resolution_status": "ambiguous", "candidates": [{"id": "P1"}]}]}
    resolved = {"entities": [{"entity_type": "product", "resolution_status": "resolved", "resolved": {"id": "P1"}}]}
    assert not equivalent(ambiguous, resolved, context)


def test_gold_data_conflict_is_not_masked(context):
    gold = {"entities": [{"entity_type": "product", "surface": "葛洲坝", "resolution_status": "resolved", "resolved": {"id": "SYNTHETIC_GOLD_ID"}}]}
    actual = {"entities": [{"entity_type": "product", "surface": "葛洲坝", "resolution_status": "resolved", "resolved": {"id": "P_GZM_REAL"}}]}
    result = compare_plan_semantics(gold, actual, context)
    assert not result["equivalent"]
    assert result["semantic_differences"][0]["kind"] == "ENTITY_RESOLUTION_OR_ID_MISMATCH"
