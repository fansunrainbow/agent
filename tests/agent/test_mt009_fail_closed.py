from __future__ import annotations

from agent.orchestrator import AgentOrchestrator


def _follow(agent: AgentOrchestrator, first: str, second: str):
    parent = agent.run(first)
    return agent.run(second, {"previous_plan": parent.query_plan, "parent_plan_id": parent.query_id})


def _value(plan: dict, target: str):
    return next(item.get("value") for item in plan["filters"] if item.get("target") == target)


def test_mt009_unknown_level_replacement_fails_closed():
    state = _follow(
        AgentOrchestrator(),
        "2026年Q1南京钻石客户日均资产",
        "换成苏州普通客户",
    )
    assert state.status.value == "needs_clarification"
    audit = state.conversation_context["plan_patch"]
    failed = next(item for item in audit["changes"] if item["patch_status"] != "APPLIED")
    assert failed["patch_operation"] == "REPLACE_FILTER"
    assert failed["patch_target"] == "customer_level"
    assert failed["resolution_status"] == "not_found"
    assert audit["patch_status"] == "PARTIALLY_APPLIED"
    assert audit["status_before"] == "ready"
    assert audit["status_after"] == "needs_clarification"


def test_ambiguous_level_replacement_requires_clarification():
    state = _follow(AgentOrchestrator(), "2026年Q1钻石客户日均资产", "换成优质客户")
    assert state.status.value == "needs_clarification"
    assert state.query_plan["status"] == "needs_clarification"


def test_valid_gold_level_replacement_succeeds():
    state = _follow(AgentOrchestrator(), "2026年Q1钻石客户日均资产", "换成金卡客户")
    assert state.status.value == "ready"
    assert _value(state.query_plan, "customer_level") == "gold"
    assert state.conversation_context["plan_patch"]["patch_status"] == "APPLIED"


def test_unknown_city_never_retains_ready_status():
    state = _follow(AgentOrchestrator(), "2026年Q1南京客户数量", "换成火星城")
    assert state.status.value == "needs_clarification"
    assert _value(state.query_plan, "city") == "南京"
    assert state.conversation_context["plan_patch"]["patch_status"] == "NEEDS_CLARIFICATION"


def test_unknown_metric_never_retains_ready_status():
    state = _follow(AgentOrchestrator(), "2026年Q1南京客户数量", "换成神秘指标")
    assert state.status.value == "needs_clarification"
    assert state.query_plan["metrics"] == ["customer_count"]
    assert state.conversation_context["plan_patch"]["patch_status"] == "NEEDS_CLARIFICATION"


def test_valid_remove_still_succeeds():
    state = _follow(AgentOrchestrator(), "2026年Q1南京女性客户数量", "去掉性别条件")
    assert state.status.value == "ready"
    assert not any(item.get("target") == "gender" for item in state.query_plan["filters"])


def test_failed_mutation_is_not_presented_as_modified_ready_plan():
    state = _follow(AgentOrchestrator(), "2026年Q1南京客户数量", "换成火星城")
    assert state.query_plan["status"] != "ready"
    assert state.conversation_context["plan_patch"]["status_after"] != "ready"
    trace = next(item for item in state.trace if item.step == "apply_plan_patch")
    assert trace.status == "failed"


def test_new_task_is_not_subject_to_patch_failure_policy():
    parent = AgentOrchestrator().run("2026年Q1南京客户数量")
    state = AgentOrchestrator().run(
        "重新查2026年Q1交易次数",
        {"previous_plan": parent.query_plan, "parent_plan_id": parent.query_id},
    )
    assert state.status.value == "ready"
    assert state.query_plan["metrics"] == ["trade_count"]
    assert state.conversation_context["plan_patch"]["operation"] == "reset"
