from __future__ import annotations

import json

from agent import AgentOrchestrator
from agent.models import ToolResult
from agent.services.audit_logger import JsonlAuditLogger
from agent.tools import (
    DictionaryTool,
    DimensionTool,
    JoinTool,
    MetricTool,
    RegistryTool,
    SchemaTool,
)


def test_tool_result_failure_contract_is_uniform():
    result = ToolResult.fail("TEST_ERROR", "test", "unit-test")
    assert result.model_dump() == {
        "success": False,
        "data": None,
        "source": "unit-test",
        "confidence": 0.0,
        "error_code": "TEST_ERROR",
        "error_message": "test",
    }


def test_registry_and_metadata_tools_use_real_registries():
    assert RegistryTool().check("metric", "trade_amount").success
    assert MetricTool().get("trade_amount").data["metric_id"] == "trade_amount"
    assert DimensionTool().get("city").data["dimension_id"] == "city"
    assert DictionaryTool().get("female_customer").data["concept_id"] == "female_customer"
    assert SchemaTool().get_table("dim_product").data["table_id"] == "dim_product"


def test_unknown_registry_items_return_explicit_failures():
    result = MetricTool().get("not_a_metric")
    assert result.success is False
    assert result.error_code == "UNKNOWN_METRIC"
    assert result.confidence == 0.0


def test_join_tool_allows_verified_path_and_rejects_cross_fact_path():
    tool = JoinTool()
    safe = tool.get_path("dim_product", "dwd_cust_tran_d")
    unsafe = tool.get_path("dws_cust_aset_d", "dwd_cust_tran_d")
    assert safe.success is True
    assert safe.data["joins"][0]["verified"] is True
    assert unsafe.success is False
    assert unsafe.error_code == "UNSAFE_JOIN_PATH"


def test_audit_logger_redacts_customer_and_long_ids(tmp_path):
    path = tmp_path / "audit.jsonl"
    agent = AgentOrchestrator(audit_log=path)
    state = agent.run("查询客户C123456789012345和1234567890123456")
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert "C123456789012345" not in record["user_query"]
    assert "1234567890123456" not in record["user_query"]
    assert state.trace[-1].step == "finish"
