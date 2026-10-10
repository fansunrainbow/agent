from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from guardrail.sql_generator import ParameterBag, SQLGenerationError, SQLGenerator
from guardrail.sql_validator import SQLValidator
from scripts.validate_query_plan import validate_plan_data


ROOT = Path(__file__).resolve().parents[2]


def seed_plan(case_id: str = "SQL_S001") -> dict:
    for line in (ROOT / "benchmark" / "datasets" / "sql.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        if case["case_id"] == case_id:
            return deepcopy(case["input"]["plan"])
    raise KeyError(case_id)


def compile_plan(plan: dict):
    validation = validate_plan_data(plan)
    assert validation["valid"], validation["errors"]
    artifact = SQLGenerator().generate("stage84", plan, validation)
    report = SQLValidator().validate(artifact)
    assert report.allowed, [item.to_dict() for item in report.issues]
    return artifact


def metric_plan(metric: str, *, time: bool = True) -> dict:
    plan = seed_plan()
    plan["metrics"] = [metric]
    plan["dimensions"] = []
    plan["filters"] = []
    plan["group_by"] = []
    plan["having"] = []
    plan["order_by"] = []
    plan["limit"] = None
    plan["time_range"] = {"type": "quarter", "year": 2026, "quarter": 1} if time else None
    return plan


def test_customer_count_uses_metadata_count_distinct():
    artifact = compile_plan(metric_plan("customer_count", time=False))
    assert "COUNT(DISTINCT b.pty_id) AS customer_count" in artifact.sql


def test_customer_count_with_city_filter_is_parameterized():
    plan = metric_plan("customer_count", time=False)
    plan["dimensions"] = ["city"]
    plan["filters"] = [{"id": "f1", "type": "dimension", "target": "city", "operator": "eq", "value": "南京", "source": "explicit", "confidence": 1.0}]
    artifact = compile_plan(plan)
    assert "c.city_name = :" in artifact.sql and "南京市" in artifact.params.values()


def test_group_by_customer_count():
    plan = metric_plan("customer_count", time=False)
    plan.update(intent="group_analysis", dimensions=["city"], group_by=["city"])
    artifact = compile_plan(plan)
    assert "GROUP BY b.city" in artifact.sql


def test_average_total_asset_compiles_from_registry_expression():
    artifact = compile_plan(metric_plan("average_total_asset"))
    assert "calendar_day_count" not in artifact.sql and "dws_cust_aset_d" in artifact.sql


def test_trade_amount_uses_registered_fact_time_field():
    artifact = compile_plan(metric_plan("trade_amount"))
    assert "dwd_cust_tran_d" in artifact.sql and ".data_dt BETWEEN" in artifact.sql


def test_dual_metric_compiles_separate_ctes():
    plan = metric_plan("average_total_asset")
    plan["metrics"] = ["average_total_asset", "trade_amount"]
    artifact = compile_plan(plan)
    assert "metric_average_total_asset AS" in artifact.sql
    assert "metric_trade_amount AS" in artifact.sql


def test_branch_dimension_uses_verified_join():
    plan = metric_plan("customer_count", time=False)
    plan.update(intent="group_analysis", subject="branch", dimensions=["parent_branch"], group_by=["parent_branch"])
    artifact = compile_plan(plan)
    assert "JOIN dim_branch AS d_branch ON c.org_id = d_branch.org_id" in artifact.sql


def test_product_category_uses_fact_bridge_and_product_join():
    plan = metric_plan("holding_market_value")
    plan.update(intent="group_analysis", subject="product", dimensions=["product_secondary_category"], group_by=["product_secondary_category"])
    artifact = compile_plan(plan)
    assert "JOIN dwd_cust_hold_d AS x_product" in artifact.sql
    assert "JOIN dim_product AS d_product" in artifact.sql


def test_between_filter_is_parameterized():
    plan = metric_plan("customer_count", time=False)
    plan["dimensions"] = ["age"]
    plan["filters"] = [{"id": "f1", "type": "dimension", "target": "age", "operator": "between", "value": [30, 50], "source": "explicit", "confidence": 1.0}]
    artifact = compile_plan(plan)
    assert "c.cust_age BETWEEN" in artifact.sql and {30, 50} <= set(artifact.params.values())


def test_in_filter_is_parameterized():
    plan = metric_plan("customer_count", time=False)
    plan["dimensions"] = ["city"]
    plan["filters"] = [{"id": "f1", "type": "dimension", "target": "city", "operator": "in", "value": ["南京", "苏州"], "source": "explicit", "confidence": 1.0}]
    artifact = compile_plan(plan)
    assert "c.city_name IN" in artifact.sql


def test_not_in_filter_is_parameterized():
    plan = metric_plan("customer_count", time=False)
    plan["dimensions"] = ["city"]
    plan["filters"] = [{"id": "f1", "type": "dimension", "target": "city", "operator": "not_in", "value": ["南京", "苏州"], "source": "explicit", "confidence": 1.0}]
    artifact = compile_plan(plan)
    assert "c.city_name NOT IN" in artifact.sql


def test_exists_uses_correlated_exists():
    sql = SQLGenerator()._entity_predicate(
        {"type": "entity", "target": "held_product", "operator": "exists"}, ParameterBag(), None,
    )
    assert "EXISTS (SELECT" in sql and "SUM(" not in sql


def test_not_exists_uses_correlated_not_exists():
    sql = SQLGenerator()._entity_predicate(
        {"type": "entity", "target": "held_product", "operator": "not_exists"}, ParameterBag(), None,
    )
    assert "NOT EXISTS (SELECT" in sql


def test_group_by_dimension_projects_registered_field():
    plan = metric_plan("total_asset")
    plan.update(intent="group_analysis", dimensions=["gender"], group_by=["gender"])
    artifact = compile_plan(plan)
    assert "c.gender_cd AS gender" in artifact.sql and "GROUP BY b.gender" in artifact.sql


def test_having_uses_aggregate_metric_expression():
    plan = metric_plan("customer_count", time=False)
    plan.update(intent="group_analysis", dimensions=["city"], group_by=["city"])
    plan["having"] = [{"id": "h1", "type": "metric", "target": "customer_count", "operator": "gt", "value": 10, "source": "explicit", "confidence": 1.0}]
    artifact = compile_plan(plan)
    assert "HAVING COUNT(DISTINCT b.pty_id) >" in artifact.sql


def test_ranking_orders_by_metric():
    plan = metric_plan("total_asset")
    plan.update(intent="ranking", order_by=[{"field": "total_asset", "direction": "desc"}], limit=20)
    artifact = compile_plan(plan)
    assert "ORDER BY total_asset DESC" in artifact.sql


def test_top_k_limit_is_parameterized():
    plan = metric_plan("total_asset")
    plan.update(intent="ranking", order_by=[{"field": "total_asset", "direction": "desc"}], limit=20)
    artifact = compile_plan(plan)
    assert artifact.sql.rstrip().endswith(next(key for key, value in ((f":{k}", v) for k, v in artifact.params.items()) if value == 20))


def test_multi_fact_metrics_are_preaggregated_before_merge():
    plan = metric_plan("average_total_asset")
    plan["metrics"] = ["average_total_asset", "trade_amount", "net_inflow"]
    artifact = compile_plan(plan)
    assert all(item["preaggregated"] for item in artifact.logical_plan["joins"])
    assert artifact.logical_plan["required_metrics"] == plan["metrics"]
    assert artifact.logical_plan["output_grain"] == ["customer"]
    assert "JOIN dwd_cust_tran_d" not in " ".join(line for line in artifact.sql.splitlines() if "dws_cust_aset_d AS" in line)


def test_invalid_product_join_is_rejected():
    with pytest.raises(SQLGenerationError) as caught:
        SQLGenerator()._verified_join_condition("ads_cust_info_d", "c", "dim_product", "p")
    assert caught.value.code == "SQL_UNSUPPORTED_COMBINATION"


def test_unsupported_subject_combination_is_rejected():
    plan = metric_plan("holding_market_value")
    plan["metrics"] = ["holding_market_value", "trade_amount"]
    plan.update(intent="group_analysis", subject="product", dimensions=["product_secondary_category"], group_by=["product_secondary_category"])
    validation = validate_plan_data(plan)
    assert validation["valid"]
    with pytest.raises(SQLGenerationError) as caught:
        SQLGenerator().generate("unsupported", plan, validation)
    assert caught.value.code == "SQL_UNSUPPORTED_COMBINATION"


def test_all_38_registered_metric_contracts_compile():
    generator = SQLGenerator()
    compiled = []
    for metric_id in generator.catalog.metrics:
        plan = metric_plan(metric_id)
        validation = validate_plan_data(plan)
        assert validation["valid"], {metric_id: validation["errors"]}
        artifact = generator.generate(f"metric-audit-{metric_id}", plan, validation)
        assert metric_id in artifact.metric_aliases
        compiled.append(metric_id)
    assert len(compiled) == 38
