from __future__ import annotations

import pytest

from agent import AgentOrchestrator


def _agent(query: str, context: dict | None = None):
    return AgentOrchestrator().run(query, context)


def test_subject_customer_is_not_a_dimension():
    state = _agent("南京客户有多少？")
    assert state.status == "ready"
    assert state.query_plan["subject"] == "customer"
    assert "customer" not in state.query_plan["dimensions"]


@pytest.mark.parametrize("surface", ["客户数量", "客户数", "客户人数", "人数", "有多少客户"])
def test_customer_count_synonyms_share_one_registered_metric(surface: str):
    state = _agent(f"南京{surface}")
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["customer_count"]


def test_metric_and_product_category_do_not_become_an_entity():
    state = _agent("2026年Q1股票交易额超过10万的客户")
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["stock_trade_amount"]
    assert not state.resolved_entities
    assert any(item.scope == "metric:stock_trade_amount" for item in state.grounded_conditions)


def test_true_product_entity_uses_dataset_resolution():
    state = _agent("贵州茅台持仓客户")
    assert state.status == "ready"
    assert state.resolved_entities[0]["status"] == "resolved"
    assert state.query_plan["filters"][0]["target"] == "held_product"


def test_ambiguous_entity_fails_closed():
    state = _agent("持有建板花旗六乙购Ａ的客户")
    assert state.status == "needs_clarification"
    assert state.resolved_entities[0]["status"] == "ambiguous"
    assert any(item.code == "AMBIGUOUS_ENTITY" for item in state.clarification.questions)


def test_nonexistent_entity_is_not_invented():
    state = _agent("持有绝对不存在产品XYZ的客户")
    assert state.status == "needs_clarification"
    assert state.resolved_entities[0]["status"] == "not_found"
    assert not state.query_plan["entities"]


def test_absolute_date_is_normalized():
    state = _agent("查询2026年3月1日交易额")
    assert state.status == "ready"
    assert state.query_plan["time_range"] == {"type": "absolute_date", "date": "2026-03-01"}


def test_month_is_normalized():
    state = _agent("查询2026年3月交易额")
    assert state.status == "ready"
    assert state.query_plan["time_range"] == {"type": "month", "year": 2026, "month": 3}


def test_chinese_quarter_is_normalized():
    state = _agent("查询2026年第一季度交易额")
    assert state.status == "ready"
    assert state.query_plan["time_range"] == {"type": "quarter", "year": 2026, "quarter": 1}


def test_relative_time_requires_reference_and_uses_context_when_available():
    unresolved = _agent("查询最近30天交易额")
    assert unresolved.status == "needs_clarification"
    assert "参考日期" in unresolved.clarification.questions[0].question
    resolved = _agent("查询最近30天交易额", {"reference_date": "2026-03-31"})
    assert resolved.status == "ready"
    assert resolved.query_plan["time_range"] == {
        "type": "date_range", "start": "2026-03-02", "end": "2026-03-31",
    }


def test_missing_required_time_remains_clarification():
    state = _agent("查询日均资产")
    assert state.status == "needs_clarification"
    assert any("统计时间" in item.question or "统计期间" in item.question for item in state.clarification.questions)
    raw_id = _agent("查询标准指标 buy_amount")
    assert raw_id.status == "needs_clarification"
    assert raw_id.query_plan["time_range"] is None


def test_prediction_request_is_unsupported():
    state = _agent("找出一定会购买产品的客户")
    assert state.status == "unsupported"
    assert any(item.code == "UNSUPPORTED_PREDICTION" for item in state.clarification.questions)


def test_suitability_request_needs_registered_suitability_data():
    state = _agent("推荐最适合客户购买的具体基金")
    assert state.status == "unsupported"
    assert any(item.code == "SUITABILITY_DATA_REQUIRED" for item in state.clarification.questions)


def test_unsupported_attribute_is_explicitly_rejected():
    state = _agent("按客户满意度评分筛选客户")
    assert state.status == "unsupported"
    assert any(item.code == "UNSUPPORTED_ATTRIBUTE" for item in state.clarification.questions)


def test_unregistered_phrase_does_not_create_a_fake_filter():
    state = _agent("筛选神秘高价值客户")
    assert state.status == "needs_clarification"
    assert not any(
        item.get("target") == "神秘高价值" for item in (state.query_plan or {}).get("filters", [])
    )


def test_low_confidence_entity_never_auto_resolves():
    state = _agent("江苏分公司客户")
    assert state.status == "needs_clarification"
    assert state.resolved_entities[0]["status"] == "ambiguous"
    candidates = state.resolved_entities[0]["candidates"]
    assert len(candidates) >= 2
    assert candidates[0]["score"] - candidates[1]["score"] < 0.08
