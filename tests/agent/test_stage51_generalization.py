from __future__ import annotations

from copy import deepcopy

from agent import AgentOrchestrator
from agent.llm import StaticStructuredProvider
from agent.services.context_manager import ContextManager


def _filter(plan: dict, target: str) -> dict:
    return next(item for item in plan["filters"] if item.get("target") == target)


def _next_context(state) -> dict:
    context = dict(state.conversation_context)
    context["previous_plan"] = state.query_plan
    context["parent_plan_id"] = state.query_id
    return context


def test_four_condition_filters_are_grounded_independently():
    state = AgentOrchestrator().run(
        "筛选2026年Q1南京地区、女性、基金持仓占比低于10%、净流入为正的客户。"
    )
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["fund_holding_ratio", "net_inflow"]
    assert _filter(state.query_plan, "city")["value"] == "南京"
    assert _filter(state.query_plan, "gender")["value"] == "female"
    assert (_filter(state.query_plan, "fund_holding_ratio")["operator"], _filter(state.query_plan, "fund_holding_ratio")["value"]) == ("lt", 0.1)
    assert (_filter(state.query_plan, "net_inflow")["operator"], _filter(state.query_plan, "net_inflow")["value"]) == ("gt", 0)
    assert all(item.original_surface for item in state.grounded_conditions)


def test_new_double_metric_combination_has_no_redundant_semantics():
    state = AgentOrchestrator().run(
        "找2026年Q1日均资产超过50万，同时股票交易额超过10万的客户。"
    )
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["average_total_asset", "stock_trade_amount"]
    assert "trade_amount" not in state.query_plan["metrics"]
    assert "product_primary_category" not in state.query_plan["dimensions"]
    assert not state.resolved_entities
    assert state.validation_result["valid"] is True


def test_metric_with_product_category_is_typed_not_entity():
    state = AgentOrchestrator().run("2026年Q1股票交易额超过10万的客户")
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["stock_trade_amount"]
    scoped = [
        item for item in state.grounded_conditions
        if item.semantic_type == "dimension" and item.target == "product_primary_category"
    ]
    assert len(scoped) == 1
    assert scoped[0].value == "股票"
    assert scoped[0].scope == "metric:stock_trade_amount"
    assert not state.resolved_entities


def test_unknown_dimension_clarification_is_precise_and_offers_alternatives():
    state = AgentOrchestrator().run("查询已婚客户中资产最高的20个人。")
    assert state.status == "needs_clarification"
    question = next(item for item in state.clarification.questions if item.term == "已婚")
    assert "不支持维度条件“已婚”" in question.question
    assert question.options
    assert all("dimension_id" in item for item in question.options)
    assert state.query_plan["metrics"] == ["total_asset"]
    assert state.query_plan["limit"] == 20


def test_three_turn_plan_patch_preserves_metric_time_and_filters():
    agent = AgentOrchestrator()
    first = agent.run("2026年Q1南京客户平均资产是多少？")
    second = agent.run("只看钻石客户。", _next_context(first))
    third = agent.run("换成苏州。", _next_context(second))

    assert first.query_plan["metrics"] == ["average_total_asset"]
    assert third.status == "ready"
    assert third.query_plan["metrics"] == ["average_total_asset"]
    assert third.query_plan["time_range"] == {"type": "quarter", "year": 2026, "quarter": 1}
    assert _filter(third.query_plan, "customer_level")["value"] == "diamond"
    assert _filter(third.query_plan, "city")["value"] == "苏州"
    assert len({item["id"] for item in third.query_plan["filters"]}) == len(third.query_plan["filters"])
    assert third.conversation_context["plan_patch"]["changes"][0]["action"] == "REPLACE_FILTER"


def test_patch_engine_supports_all_required_operations():
    engine = ContextManager()
    assert engine.SUPPORTED_ACTIONS == {
        "ADD_FILTER", "REMOVE_FILTER", "REPLACE_FILTER",
        "ADD_METRIC", "REMOVE_METRIC", "REPLACE_METRIC",
        "CHANGE_TIME_RANGE", "REMOVE_TIME_RANGE",
        "CHANGE_ORDER", "REMOVE_ORDER", "CHANGE_LIMIT", "REMOVE_LIMIT",
        "ADD_DIMENSION", "REMOVE_DIMENSION", "REPLACE_DIMENSION",
    }
    base = AgentOrchestrator().run("南京客户数量").query_plan
    fragment = deepcopy(base)
    fragment["metrics"] = ["trade_amount"]
    fragment["filters"] = [{
        "id": "pending", "type": "dimension", "target": "city", "operator": "eq",
        "value": "苏州", "source": "explicit", "confidence": 1.0,
    }]
    fragment["time_range"] = {"type": "year", "year": 2026}
    fragment["order_by"] = [{"field": "trade_amount", "direction": "desc"}]
    fragment["limit"] = 5
    changed, _ = engine.apply(base, fragment, requested_operations=[
        {"action": "REPLACE_FILTER", "target": "city"},
        {"action": "ADD_METRIC", "target": "trade_amount"},
        {"action": "CHANGE_TIME_RANGE", "target": "time_range"},
        {"action": "CHANGE_ORDER", "target": "order_by"},
        {"action": "CHANGE_LIMIT", "target": "limit"},
    ])
    assert {"customer_count", "trade_amount"} == set(changed["metrics"])
    assert _filter(changed, "city")["value"] == "苏州"
    assert changed["time_range"] == {"type": "year", "year": 2026}
    assert changed["limit"] == 5

    removed, _ = engine.apply(changed, {**fragment, "filters": [], "metrics": []}, requested_operations=[
        {"action": "REMOVE_FILTER", "target": "city"},
        {"action": "REMOVE_METRIC", "target": "customer_count"},
    ])
    assert not any(item.get("target") == "city" for item in removed["filters"])
    assert "customer_count" not in removed["metrics"]

    replaced, _ = engine.apply(removed, fragment, requested_operations=[
        {"action": "REPLACE_METRIC", "target": "trade_amount"},
    ])
    assert replaced["metrics"] == ["trade_amount"]


def test_registered_but_ungrounded_provider_semantic_is_rejected():
    base = AgentOrchestrator().run("南京客户数量").query_plan
    base["metrics"] = ["total_asset"]
    provider_agent = AgentOrchestrator(provider=StaticStructuredProvider(response=base))
    state = provider_agent.run("南京客户数量")
    assert state.status == "needs_clarification"
    assert any(error["code"] == "UNGROUNDED_SEMANTIC" for error in state.validation_result["errors"])
