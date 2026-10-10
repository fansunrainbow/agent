from __future__ import annotations

import json
from pathlib import Path

from guardrail.execution_manager import ExecutionManager
from guardrail.result_validator import ResultValidator
from guardrail.sql_generator import SQLGenerator
from scripts.validate_query_plan import validate_plan_data


ROOT = Path(__file__).resolve().parents[2]


def artifact():
    plan = json.loads((ROOT / "tests" / "query_plan" / "C011_Q1双指标阈值.json").read_text(encoding="utf-8"))["plan"]
    return SQLGenerator().generate("execute", plan, validate_plan_data(plan))


def test_empty_result_is_warning_not_hallucinated_success_data():
    check = ResultValidator().check([], artifact())
    assert check.allowed
    assert {item.code for item in check.warnings} == {"EMPTY_RESULT"}


def test_non_finite_and_duplicate_amplification_are_blocked():
    value = artifact()
    value.selected_columns = ["pty_id", "average_total_asset", "stock_trade_amount"]
    rows = [("c1", float("nan"), 1), ("c1", 2, 3)]
    check = ResultValidator().check(rows, value)
    codes = {item.code for item in check.errors}
    assert "NON_FINITE_RESULT" in codes
    assert "DUPLICATE_AMPLIFICATION" in codes


class FakeCursor:
    description = [("pty_id",), ("average_total_asset",), ("stock_trade_amount",)]

    def __init__(self):
        self.received = None

    def execute(self, sql, params):
        self.received = (sql, params)

    def fetchmany(self, count):
        return [("c1", 600000, 120000)]


class FakeConnection:
    def __init__(self):
        self.read_only = False
        self.cursor_value = FakeCursor()

    def set_session(self, readonly=False):
        self.read_only = readonly

    def cursor(self):
        return self.cursor_value


def test_execution_revalidates_and_enforces_read_only_session():
    value = artifact()
    connection = FakeConnection()
    result = ExecutionManager().execute(value, connection)
    assert result.status == "success"
    assert connection.read_only is True
    assert connection.cursor_value.received == (value.sql, value.params)
    assert result.trace.attempts == 1
    assert result.trace.validation["allowed"] is True


def test_connection_without_read_only_contract_is_rejected():
    class UnsafeConnection:
        read_only = False

    result = ExecutionManager().execute(artifact(), UnsafeConnection())
    assert result.status == "execution_error"
    assert result.trace.error["code"] == "DB_PERMISSION_DENIED"
