from __future__ import annotations

from decimal import Decimal

from agent.orchestrator import AgentOrchestrator
from benchmark.loader import available_suites
from guardrail.catalog import MetadataCatalog
from guardrail.result_normalizer import ResultNormalizer
from guardrail.sql_generator import SQLGenerator
from guardrail.sql_validator import SQLValidator


def compile_query(query: str):
    state = AgentOrchestrator().run(query)
    assert state.status.value == "ready", state.clarification
    return state, SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)


def test_enum_normalization_contract_is_metadata_driven():
    catalog = MetadataCatalog()
    assert catalog.storage_value("gender", "女") == "5000003"
    assert catalog.storage_value("gender", "F") == "5000003"
    assert catalog.storage_value("gender", "female") == "5000003"
    assert catalog.storage_value("customer_level", "diamond") == "1000001"
    assert catalog.storage_value("product_primary_category", "stock") == "股票"
    assert catalog.storage_value("city", "南京") == "南京市"


def test_metric_question_is_not_promoted_to_segment_filter():
    state, artifact = compile_query("2026年Q1客户净流入是多少？")
    assert state.query_plan["intent"] == "metric_query"
    assert state.query_plan["filters"] == []
    assert "SUM(m_net_inflow.net_inflow)" in artifact.sql


def test_group_metric_predicate_is_having():
    state, artifact = compile_query("按城市统计客户数，只显示客户数大于2的城市")
    assert state.query_plan["filters"] == []
    assert state.query_plan["having"][0]["target"] == "customer_count"
    assert "HAVING COUNT(DISTINCT b.pty_id) >" in artifact.sql


def test_ranking_keeps_entity_metric_and_stable_tie_breaker():
    _, artifact = compile_query("2026年Q1交易额最高的前20名客户")
    assert artifact.selected_columns == ["pty_id", "trade_amount"]
    assert "m_trade_amount.trade_amount AS trade_amount" in artifact.sql
    assert "ORDER BY trade_amount DESC, pty_id ASC" in artifact.sql


def test_period_end_uses_effective_available_date():
    _, artifact = compile_query("2026年Q1末客户现金资产是多少？")
    assert "SELECT MAX(effective_cash_asset.data_dt)" in artifact.sql
    assert "BETWEEN" in artifact.sql


def test_monthly_time_series_has_bucket_group_and_order():
    _, artifact = compile_query("2026年Q1按月查看净流入趋势")
    assert artifact.selected_columns == ["month", "net_inflow"]
    assert "SUBSTRING(ts.data_dt" in artifact.sql
    assert "GROUP BY" in artifact.sql and "ORDER BY month ASC" in artifact.sql


def test_known_correlated_not_exists_passes_guardrail():
    state, artifact = compile_query("2026年Q1南京客户中没有持有贵州茅台的客户")
    assert any(item["operator"] == "not_exists" for item in state.query_plan["filters"] if item["type"] == "entity")
    report = SQLValidator().validate(artifact)
    assert report.allowed, [item.to_dict() for item in report.issues]


def test_product_metric_uses_deduplicated_semijoin():
    _, artifact = compile_query("2026年Q1股票产品交易额是多少？")
    assert "IN (SELECT DISTINCT" in artifact.sql
    assert "FROM dim_product" in artifact.sql


def test_result_normalizer_handles_driver_types_and_time_order():
    _, artifact = compile_query("2026年Q1按月查看净流入趋势")
    rows = [("202602", Decimal("2.50")), ("202601", Decimal("1.00"))]
    assert ResultNormalizer.normalize(rows, ["month", "net_inflow"], artifact) == [
        {"month": "202601", "net_inflow": 1}, {"month": "202602", "net_inflow": 2.5},
    ]


def test_real_db_gold_is_not_a_legacy_suite():
    assert "real_db_gold" not in available_suites()
