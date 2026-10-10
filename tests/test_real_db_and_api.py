from __future__ import annotations

import json
import sys

import pytest
from pydantic import ValidationError

from database.config import DatabaseConfig
from database.mysql import MySQLReadOnlyConnection, _CursorAdapter
from webapp.api import ChatRequest, health
from webapp.service import ApplicationService
from scripts import run_web


def test_database_config_requires_environment(monkeypatch, tmp_path):
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="DB_HOST"):
        DatabaseConfig.from_env(tmp_path / ".env")


def test_database_config_masks_password():
    config = DatabaseConfig("localhost", 3306, "db", "reader", "secret")
    assert "secret" not in str(config.safe_summary())
    assert config.safe_summary()["password"] == "***"


def test_mysql_parameter_adapter_never_interpolates_values():
    assert _CursorAdapter._bind("SELECT * FROM t WHERE city=:p1 AND amount>:p2") == "SELECT * FROM t WHERE city=%(p1)s AND amount>%(p2)s"


class CapabilityCursor:
    def __init__(self, grants):
        self.grants = grants
        self.mode = None

    def execute(self, sql, params=None):
        self.mode = sql

    def fetchone(self):
        return (1,)

    def fetchall(self):
        return [(item,) for item in self.grants]


class CapabilityRaw:
    def __init__(self, grants):
        self.value = CapabilityCursor(grants)

    def cursor(self):
        return self.value


def _config():
    return DatabaseConfig("localhost", 3306, "agentic_marketing", "agent_readonly_user", "x")


def test_capability_accepts_select_only_grant():
    connection = MySQLReadOnlyConnection(CapabilityRaw(["GRANT SELECT ON `agentic_marketing`.* TO `agent_readonly_user`@`%`"]), _config())
    result = connection.capability_check()
    assert result.connected and result.select_allowed and result.readonly_verified


def test_capability_rejects_write_grant_without_probing_writes():
    raw = CapabilityRaw(["GRANT SELECT, UPDATE ON `agentic_marketing`.* TO `agent_readonly_user`@`%`"])
    result = MySQLReadOnlyConnection(raw, _config()).capability_check()
    assert not result.readonly_verified and result.forbidden_privileges == ["UPDATE"]
    assert raw.value.mode == "SHOW GRANTS FOR CURRENT_USER"


def test_api_contract_rejects_raw_sql():
    with pytest.raises(ValidationError):
        ChatRequest(message="南京客户有多少？", sql="DROP TABLE x")


def test_health_marks_dry_run_without_credentials(monkeypatch):
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    payload = health()
    assert payload["mode"] == "DEMO / DRY RUN"
    assert payload["raw_sql_api"] is False


def test_health_marks_dry_run_when_database_is_unreachable(monkeypatch):
    for key, value in {"DB_HOST": "127.0.0.1", "DB_NAME": "db", "DB_USER": "reader", "DB_PASSWORD": "example"}.items():
        monkeypatch.setenv(key, value)

    def fail_connection(_config):
        raise OSError("database unavailable")

    monkeypatch.setattr("webapp.service.create_readonly_connection", fail_connection)
    assert health()["mode"] == "DEMO / DRY RUN"


def test_application_service_ready_chat_exposes_sql_and_params_separately():
    value = ApplicationService().chat("南京客户有多少？")
    assert value["status"] == "ready"
    assert value["sql"] and value["params"]
    assert "南京" not in value["sql"]
    assert "南京市" in value["params"].values()


def test_application_service_clarification_is_not_internal_error():
    value = ApplicationService().chat("筛选日均资产超过50万的客户。")
    assert value["status"] == "needs_clarification"
    assert value["message"]


def test_benchmark_summary_does_not_invent_real_db_metrics():
    value = ApplicationService().benchmark_summary()
    assert value["real_db_status"] in {"MEASURED", "NOT_MEASURED"}
    if value["real_db_status"] == "NOT_MEASURED":
        assert value["real_db"] is None


def test_web_runner_rejects_remote_bind_without_explicit_acknowledgement(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_web.py", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit, match="Refusing non-loopback bind"):
        run_web.main()
