from __future__ import annotations

from copy import deepcopy

import pytest

from agent import AgentOrchestrator
from agent.benchmark import evaluate
from agent.llm import StaticStructuredProvider
from agent.repair import RepairEngine
from agent.tools import RegistryTool
from scripts.validate_query_plan import validate_plan_data


@pytest.fixture(scope="module")
def orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator()


def test_simple_count_query_is_grounded(orchestrator: AgentOrchestrator):
    state = orchestrator.run("南京客户有多少？")
    assert state.status == "ready"
    assert state.query_plan["metrics"] == ["customer_count"]
    assert any(item.get("target") == "city" and item.get("value") == "南京" for item in state.query_plan["filters"])
    assert state.validation_result["valid"] is True


def test_complex_query_parses_time_metric_filter_and_concept(orchestrator: AgentOrchestrator):
    state = orchestrator.run("2024年Q1南京女性客户日均资产超过100万")
    assert state.status == "ready"
    assert state.query_plan["time_range"] == {"type": "quarter", "year": 2024, "quarter": 1}
    assert "average_total_asset" in state.query_plan["metrics"]
    assert any(item.get("target") == "average_total_asset" and item.get("value") == 1_000_000 for item in state.query_plan["filters"])
    assert state.validation_result["valid"] is True


def test_ranking_uses_registered_metric_and_product_subject(orchestrator: AgentOrchestrator):
    state = orchestrator.run("交易金额最高的前10个产品")
    assert state.status == "ready"
    assert state.query_plan["intent"] == "ranking"
    assert state.query_plan["subject"] == "product"
    assert state.query_plan["order_by"] == [{"field": "trade_amount", "direction": "desc"}]
    assert state.query_plan["limit"] == 10


def test_ambiguous_metric_and_missing_time_require_clarification(orchestrator: AgentOrchestrator):
    state = orchestrator.run("平均资产")
    assert state.status == "needs_clarification"
    codes = {item.code for item in state.clarification.questions}
    assert "AMBIGUOUS_METRIC" in codes
    assert "AMBIGUOUS_TIME" in codes


@pytest.mark.parametrize("query", ["火星能量值超过10的客户", "已婚客户"])
def test_unknown_semantics_are_never_invented(orchestrator: AgentOrchestrator, query: str):
    state = orchestrator.run(query)
    assert state.status == "needs_clarification"
    registry = RegistryTool()
    assert all(metric in registry.ids("metric") for metric in state.query_plan["metrics"])
    assert all(dimension in registry.ids("dimension") for dimension in state.query_plan["dimensions"])


def test_new_product_id_is_resolved_from_dataset_not_hardcoded(orchestrator: AgentOrchestrator):
    state = orchestrator.run("持有9900000209的客户")
    assert state.status == "ready"
    assert state.query_plan["entities"][0]["resolved"]["id"] == "9900000209"
    assert "dim_product" in state.grounding_sources[-1]["source"] or any(
        "dim_product" in str(item.get("source")) for item in state.grounding_sources
    )


def test_duplicate_product_name_requires_disambiguation(orchestrator: AgentOrchestrator):
    state = orchestrator.run("持有建板花旗六乙购Ａ的客户")
    assert state.status == "needs_clarification"
    entity_question = next(item for item in state.clarification.questions if item.code == "AMBIGUOUS_ENTITY")
    assert len(entity_question.options) >= 2


def test_follow_up_context_replaces_city_without_losing_metric(orchestrator: AgentOrchestrator):
    first = orchestrator.run("南京客户数量")
    second = orchestrator.run("改为苏州", {"previous_plan": first.query_plan, "parent_plan_id": first.query_id})
    assert second.status == "ready"
    assert second.query_plan["metrics"] == ["customer_count"]
    assert any(item.get("target") == "city" and item.get("value") == "苏州" for item in second.query_plan["filters"])
    assert not any(item.get("target") == "city" and item.get("value") == "南京" for item in second.query_plan["filters"])
    assert second.query_plan["context"]["operation"] == "refine"


def test_repair_is_canonical_only_and_bounded(orchestrator: AgentOrchestrator):
    valid = orchestrator.run("南京客户数量").query_plan
    invalid = deepcopy(valid)
    invalid["filters"][0]["operator"] = "="
    validation = validate_plan_data(invalid)
    engine = RepairEngine()
    assert engine.MAX_ATTEMPTS == 2
    assert engine.is_repairable(validation)
    repaired, info = engine.repair(invalid, validation)
    assert info["changed"] is True
    assert repaired["filters"][0]["operator"] == "eq"
    assert validate_plan_data(repaired)["valid"] is True


def test_provider_cannot_bypass_stage4_semantic_validation(orchestrator: AgentOrchestrator):
    base = orchestrator.run("南京客户数量").query_plan
    base["metrics"] = ["invented_metric"]
    provider_agent = AgentOrchestrator(provider=StaticStructuredProvider(response=base))
    state = provider_agent.run("请查询一个模型虚构的指标")
    assert state.status == "needs_clarification"
    assert state.validation_result["valid"] is False
    assert any(error["code"] == "UNKNOWN_METRIC" for error in state.validation_result["errors"])


def test_benchmark_reports_zero_semantic_hallucinations(orchestrator: AgentOrchestrator):
    states = [orchestrator.run("南京客户数量"), orchestrator.run("交易金额最高的前10个产品")]
    result = evaluate(states)
    assert result.semantic_hallucination_count == 0
    assert result.semantic_hallucination_rate == 0.0
