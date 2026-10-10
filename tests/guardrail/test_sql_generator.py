from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from guardrail.sql_generator import SQLGenerationError, SQLGenerator
from guardrail.sql_validator import SQLValidator
from scripts.validate_query_plan import validate_plan_data


ROOT = Path(__file__).resolve().parents[2]


def load_plan(name: str) -> dict:
    return json.loads((ROOT / "tests" / "query_plan" / name).read_text(encoding="utf-8"))["plan"]


def test_only_accepts_ready_validated_plan():
    plan = load_plan("C011_Q1双指标阈值.json")
    with pytest.raises(SQLGenerationError, match="有效验证结果"):
        SQLGenerator().generate("q1", plan, None)
    plan["status"] = "needs_clarification"
    with pytest.raises(SQLGenerationError, match="status=ready"):
        SQLGenerator().generate("q1", plan, {"valid": True})


def test_stage4_is_revalidated_internally():
    plan = load_plan("C011_Q1双指标阈值.json")
    plan["metrics"].append("hallucinated_metric")
    with pytest.raises(SQLGenerationError) as caught:
        SQLGenerator().generate("q1", plan, {"valid": True})
    assert caught.value.code == "PLAN_REVALIDATION_FAILED"


def test_dual_metric_is_preaggregated_and_guarded():
    plan = load_plan("C011_Q1双指标阈值.json")
    validation = validate_plan_data(plan)
    artifact = SQLGenerator().generate("dual", plan, validation)
    assert "metric_average_total_asset AS" in artifact.sql
    assert "metric_stock_trade_amount AS" in artifact.sql
    assert "dws_cust_aset_d AS" in artifact.sql
    assert "dwd_cust_tran_d AS" in artifact.sql
    assert "dws_cust_aset_d" not in " ".join(line for line in artifact.sql.splitlines() if "JOIN dwd_cust_tran_d" in line)
    assert artifact.logical_plan["joins"][0]["preaggregated"] is True
    assert SQLValidator().validate(artifact).allowed


def test_four_conditions_bind_to_their_own_targets():
    plan = load_plan("C011_Q1双指标阈值.json")
    plan["dimensions"] = ["city", "gender"]
    plan["filters"] = [
        {"id": "f1", "type": "dimension", "target": "city", "operator": "eq", "value": "南京", "source": "explicit", "confidence": 1.0},
        {"id": "f2", "type": "dimension", "target": "gender", "operator": "eq", "value": "F", "source": "explicit", "confidence": 1.0},
        {"id": "f3", "type": "metric", "target": "average_total_asset", "operator": "gt", "value": 500000, "source": "explicit", "confidence": 1.0},
        {"id": "f4", "type": "metric", "target": "stock_trade_amount", "operator": "gt", "value": 100000, "source": "explicit", "confidence": 1.0},
    ]
    validation = validate_plan_data(plan)
    assert validation["valid"], validation["errors"]
    artifact = SQLGenerator().generate("four", plan, validation)
    assert "c.city_name =" in artifact.sql
    assert "c.gender_cd =" in artifact.sql
    assert "m_average_total_asset.average_total_asset >" in artifact.sql
    assert "m_stock_trade_amount.stock_trade_amount >" in artifact.sql
    assert set(artifact.params.values()) >= {"南京市", "5000003", 500000, 100000}
    assert SQLValidator().validate(artifact).allowed


def test_injection_value_stays_out_of_sql():
    plan = load_plan("C011_Q1双指标阈值.json")
    plan["dimensions"] = ["city"]
    attack = "南京' OR 1=1 --"
    plan["filters"] = [{"id": "f1", "type": "dimension", "target": "city", "operator": "eq", "value": attack, "source": "explicit", "confidence": 1.0}]
    validation = validate_plan_data(plan)
    assert validation["valid"], validation["errors"]
    artifact = SQLGenerator().generate("inject", plan, validation)
    assert attack not in artifact.sql
    assert attack in artifact.params.values()
    assert SQLValidator().validate(artifact).allowed


def test_metric_product_category_uses_verified_product_join():
    plan = load_plan("C011_Q1双指标阈值.json")
    plan["metrics"] = ["stock_trade_amount"]
    plan["filters"] = []
    validation = validate_plan_data(plan)
    artifact = SQLGenerator().generate("category", plan, validation)
    assert "IN (SELECT DISTINCT" in artifact.sql and "FROM dim_product" in artifact.sql
    assert "up_prdt_type_name = :" in artifact.sql
    assert SQLValidator().validate(artifact).allowed
