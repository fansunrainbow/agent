from __future__ import annotations

from copy import deepcopy

import pytest

from agent.orchestrator import AgentOrchestrator
from agent.services.context_manager import ContextManager


def _base(*, metric: str = "customer_count") -> dict:
    return {
        "version": "1.0", "status": "ready", "intent": "metric_query", "subject": "customer",
        "metrics": [metric], "dimensions": ["city"],
        "filters": [{
            "id": "f1", "type": "dimension", "target": "city", "operator": "eq",
            "value": "南京", "source": "explicit", "confidence": 1.0,
        }],
        "entities": [], "time_range": {"type": "quarter", "year": 2026, "quarter": 1},
        "group_by": [], "having": [], "order_by": [], "limit": None,
        "output": {"mode": "aggregate", "format": "table", "include_details": False, "include_explanation": True},
        "ambiguities": [], "assumptions": [],
        "confidence": {"overall": 1.0}, "context": {"parent_plan_id": None, "operation": "new"},
    }


def _filter(target: str, value: object, *, kind: str = "dimension", operator: str = "eq") -> dict:
    return {
        "id": "pending", "type": kind, "target": target, "operator": operator,
        "value": value, "source": "explicit", "confidence": 1.0,
    }


def _fragment(**changes) -> dict:
    data = _base()
    data.update({"metrics": [], "dimensions": [], "filters": [], "time_range": None, "order_by": [], "limit": None, "ambiguities": []})
    data.update(changes)
    return data


def _apply(previous: dict, *, fragment: dict | None = None, operations=None, query: str = "", metrics=None):
    return ContextManager().apply(
        previous, fragment or _fragment(), requested_operations=operations or [], query=query, metrics=metrics or {},
    )[0]


def test_add_filter():
    result = _apply(_base(), fragment=_fragment(filters=[_filter("gender", "女")]))
    assert any(item.get("target") == "gender" for item in result["filters"])


def test_remove_filter_only_removes_target():
    base = _base()
    base["filters"].append(_filter("gender", "男"))
    result = _apply(base, operations=[{"action": "REMOVE_FILTER", "target": "gender"}])
    assert [item["target"] for item in result["filters"]] == ["city"]
    assert result["metrics"] == base["metrics"] and result["time_range"] == base["time_range"]


def test_replace_filter_by_semantic_target():
    result = _apply(_base(), fragment=_fragment(filters=[_filter("city", "苏州")]))
    assert result["filters"][0]["value"] == "苏州"


def test_replace_nested_filter_by_semantic_target():
    base = _base()
    base["filters"] = [{"logic": "and", "conditions": [
        _filter("city", "南京"),
        {"logic": "or", "conditions": [_filter("gender", "女"), _filter("customer_level", "1000001")]},
    ]}]
    result = _apply(base, fragment=_fragment(filters=[_filter("city", "苏州")]))
    leaves = list(ContextManager._filter_leaves(result["filters"]))
    assert [(item["target"], item["value"]) for item in leaves] == [
        ("city", "苏州"), ("gender", "女"), ("customer_level", "1000001"),
    ]


def test_add_metric():
    result = _apply(_base(), operations=[{"action": "ADD_METRIC", "target": "trade_count", "value": 20}])
    assert result["metrics"] == ["customer_count", "trade_count"]


def test_remove_metric():
    base = _base()
    base["metrics"].append("trade_count")
    result = _apply(base, operations=[{"action": "REMOVE_METRIC", "target": "customer_count"}])
    assert result["metrics"] == ["trade_count"]


def test_replace_metric_and_order_field():
    base = _base()
    base["order_by"] = [{"field": "customer_count", "direction": "desc"}]
    result = _apply(base, operations=[{"action": "REPLACE_METRIC", "target": "trade_count"}])
    assert result["metrics"] == ["trade_count"]
    assert result["order_by"][0]["field"] == "trade_count"


def test_change_time_replaces_old_range():
    time_range = {"type": "quarter", "year": 2026, "quarter": 2}
    result = _apply(_base(), fragment=_fragment(time_range=time_range))
    assert result["time_range"] == time_range


def test_remove_required_time_recomputes_to_clarification():
    base = _base(metric="average_total_asset")
    result = _apply(
        base, operations=[{"action": "REMOVE_TIME_RANGE", "target": "time_range"}],
        metrics={"average_total_asset": {"constraints": {"required_time_range": True}}},
    )
    assert result["time_range"] is None and result["status"] == "needs_clarification"


def test_change_order_retains_other_fields():
    order = [{"field": "customer_count", "direction": "desc"}]
    result = _apply(_base(), operations=[{"action": "CHANGE_ORDER", "target": "order_by", "value": order}])
    assert result["order_by"] == order and result["filters"] == _base()["filters"]


def test_remove_order_retains_limit():
    base = _base()
    base["order_by"] = [{"field": "customer_count", "direction": "desc"}]
    base["limit"] = 20
    result = _apply(base, operations=[{"action": "REMOVE_ORDER", "target": "order_by"}])
    assert result["order_by"] == [] and result["limit"] == 20


def test_change_limit_does_not_create_clarification():
    result = _apply(_base(), fragment=_fragment(limit=50), query="改成前50名")
    assert result["limit"] == 50 and result["status"] == "ready"


def test_remove_limit():
    base = _base()
    base["limit"] = 20
    result = _apply(base, query="不限制数量")
    assert result["limit"] is None


def test_clarification_follow_up_becomes_ready():
    base = _base(metric="average_total_asset")
    base.update(status="needs_clarification", time_range=None, ambiguities=[{
        "term": "统计期间", "type": "time", "reason": "缺少时间", "question": "请补充时间", "candidates": [],
    }])
    result = _apply(
        base, fragment=_fragment(time_range={"type": "quarter", "year": 2026, "quarter": 1}),
        metrics={"average_total_asset": {"constraints": {"required_time_range": True}}},
    )
    assert result["status"] == "ready" and result["metrics"] == ["average_total_asset"]


def test_ready_becomes_clarification_after_metric_removal():
    result = _apply(_base(), operations=[{"action": "REMOVE_METRIC", "target": "customer_count"}])
    assert result["status"] == "needs_clarification"


def test_keep_metric_retains_context():
    result = _apply(_base(), fragment=_fragment(ambiguities=[{"type": "other", "term": "刚才", "reason": "x"}]), query="还是看刚才那个指标")
    assert result["metrics"] == ["customer_count"] and result["status"] == "ready"


def test_keep_time_retains_context():
    result = _apply(_base(), query="时间不变")
    assert result["time_range"] == _base()["time_range"] and result["status"] == "ready"


def test_ambiguous_metric_reference_requires_clarification():
    base = _base()
    base["metrics"].append("trade_count")
    result = _apply(base, query="还是看刚才那个指标")
    assert result["status"] == "needs_clarification"


def test_unsupported_follow_up_stays_unsupported():
    base = _base()
    base.update(status="needs_clarification", ambiguities=[{
        "term": "预测购买", "type": "prediction_request", "reason": "不支持预测", "question": "请改为事实查询", "candidates": [],
    }])
    result = _apply(base, fragment=_fragment(filters=[_filter("city", "南京")]), query="那只看南京")
    assert result["status"] == "needs_clarification"
    assert any(item["type"] == "prediction_request" for item in result["ambiguities"])


def test_new_task_marker_is_not_local_patch():
    assert ContextManager.is_new_task("重新查一下有哪些产品")
    assert not ContextManager.is_new_task("换成苏州")


def test_conflicting_keep_and_replace_requires_clarification():
    result = _apply(_base(), fragment=_fragment(filters=[_filter("city", "苏州")]), query="保留南京，但换成苏州")
    assert result["status"] == "needs_clarification"


@pytest.mark.parametrize(
    ("action", "target", "new_value", "expected"),
    [
        ("ADD_DIMENSION", "gender", "gender", ["city", "gender"]),
        ("REMOVE_DIMENSION", "city", None, []),
        ("REPLACE_DIMENSION", "city", "province", ["province"]),
    ],
)
def test_dimension_patch_operations(action, target, new_value, expected):
    base = _base()
    base["filters"] = []
    result = _apply(base, operations=[{"action": action, "target": target, "value": new_value}])
    assert result["dimensions"] == expected


@pytest.fixture(scope="module")
def agent() -> AgentOrchestrator:
    return AgentOrchestrator()


def _dialogue(agent: AgentOrchestrator, turns: list[str]):
    context = {}
    states = []
    for turn in turns:
        state = agent.run(turn, context)
        states.append(state)
        if state.query_plan:
            context = {"previous_plan": state.query_plan, "parent_plan_id": state.query_id}
    return states


@pytest.mark.parametrize("turns,assertion", [
    (["2026年Q1南京客户日均资产", "只看钻石客户", "换成苏州"], lambda p: any(x.get("target") == "city" and x.get("value") == "苏州" for x in p["filters"])),
    (["2026年Q1南京客户数量", "再看交易次数", "不要客户数了"], lambda p: p["metrics"] == ["trade_count"]),
    (["2026年Q1南京客户平均资产前20名", "改成Q2", "改成前10名"], lambda p: p["time_range"]["quarter"] == 2 and p["limit"] == 10),
    (["筛选日均资产超过50万的客户", "2026年Q1", "时间不变"], lambda p: p["status"] == "ready" and p["metrics"] == ["average_total_asset"]),
    (["2026年Q1客户总资产前20名", "从低到高", "不要排序"], lambda p: p["order_by"] == [] and p["limit"] == 20),
])
def test_three_turn_dialogues(agent, turns, assertion):
    states = _dialogue(agent, turns)
    assert all(state.query_plan is not None for state in states)
    assert assertion(states[-1].query_plan)


@pytest.mark.parametrize("turns,assertion", [
    (["2026年Q1南京客户日均资产", "只看钻石客户", "换成苏州", "改成Q2", "只看前10名"], lambda p: p["status"] == "ready" and p["time_range"]["quarter"] == 2 and p["limit"] == 10),
    (["2026年Q1客户平均资产前20名", "再看交易次数", "不要交易次数了", "从低到高", "不限制数量"], lambda p: p["metrics"] == ["average_total_asset"] and p["order_by"][0]["direction"] == "asc" and p["limit"] is None),
])
def test_five_turn_dialogues(agent, turns, assertion):
    states = _dialogue(agent, turns)
    assert all(state.query_plan is not None for state in states)
    assert assertion(states[-1].query_plan)


def test_patch_audit_contains_required_fields(agent):
    states = _dialogue(agent, ["2026年Q1南京客户数量", "换成苏州"])
    audit = states[-1].conversation_context["plan_patch"]
    assert {"parent_plan_id", "patch_operation", "patch_target", "changes", "result_plan", "validation_result", "status_before", "status_after"} <= set(audit)
    assert {"old_value", "new_value"} <= set(audit["changes"][0])


def test_new_task_resets_parent_plan(agent):
    states = _dialogue(agent, ["2026年Q1南京客户数量", "重新查2026年Q1交易次数"])
    plan = states[-1].query_plan
    assert plan["metrics"] == ["trade_count"]
    assert not any(item.get("target") == "city" for item in plan["filters"])
    assert states[-1].conversation_context["plan_patch"]["operation"] == "reset"
