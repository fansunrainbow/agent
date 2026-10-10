from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
import sys

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.orchestrator import AgentOrchestrator
from database import DatabaseConfig, create_readonly_connection
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator


REPORT_DIR = ROOT / "benchmark" / "reports" / "real_db_final"
REQUIRED_ENV = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
BUSINESS_TABLES = (
    "ads_cust_info_d", "dim_branch", "dim_product", "dim_public",
    "dws_cust_aset_d", "dws_cust_fin_d", "dwd_cust_tran_d", "dwd_cust_hold_d",
)
WRITE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "ALL PRIVILEGES")
SMOKE_CASES = (
    ("SMOKE_01", "customer_count", "客户有多少？"),
    ("SMOKE_02", "city_filter", "南京客户有多少？"),
    ("SMOKE_03", "average_total_asset", "2026年Q1南京客户日均资产是多少？"),
    ("SMOKE_04", "trade_amount", "2026年Q1客户交易额是多少？"),
    ("SMOKE_05", "net_inflow", "2026年Q1客户净流入是多少？"),
    ("SMOKE_06", "branch_filter", "北京分公司客户有多少？"),
    ("SMOKE_07", "product_category_filter", "2026年Q1股票产品交易额是多少？"),
    ("SMOKE_08", "multi_metric", "2026年Q1客户日均资产和交易额是多少？"),
    ("SMOKE_09", "group_by", "按性别统计客户数量"),
    ("SMOKE_10", "ranking_top_k", "2026年Q1日均资产最高的前10名客户"),
)


def write_json(name: str, value: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def effective_env() -> tuple[dict[str, str], list[str]]:
    load_dotenv(ROOT / ".env", override=False)
    present = {key: "SET" if os.getenv(key) else "MISSING" for key in REQUIRED_ENV}
    return present, [key for key, state in present.items() if state == "MISSING"]


def verify_readonly(connection: Any, config: DatabaseConfig) -> dict[str, Any]:
    cursor = connection.raw_connection.cursor()
    cursor.execute("SELECT CURRENT_USER(), DATABASE()")
    current_user, database = cursor.fetchone()
    cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
    grants = [str(row[0]) for row in cursor.fetchall()]
    upper = "\n".join(grants).upper()
    detected = sorted(privilege for privilege in WRITE_PRIVILEGES if privilege in upper)
    select_allowed = "SELECT" in upper
    report = {
        "db_name": database,
        "current_user": current_user,
        "grants": grants,
        "select_allowed": select_allowed,
        "write_privilege_detected": detected,
        "verification_pass": bool(database == config.name and select_allowed and not detected),
    }
    write_json("readonly_verification.json", report)
    return report


def schema_reality_check(connection: Any, config: DatabaseConfig) -> dict[str, Any]:
    metadata = yaml.safe_load((ROOT / "metadata" / "tables.yaml").read_text(encoding="utf-8"))["tables"]
    cursor = connection.raw_connection.cursor()
    placeholders = ",".join(["%s"] * len(BUSINESS_TABLES))
    cursor.execute(
        "SELECT table_name, column_name, column_key, data_type "
        "FROM information_schema.columns WHERE table_schema=%s "
        f"AND table_name IN ({placeholders}) ORDER BY table_name, ordinal_position",
        (config.name, *BUSINESS_TABLES),
    )
    actual: dict[str, dict[str, Any]] = {}
    for table, column, column_key, data_type in cursor.fetchall():
        item = actual.setdefault(table, {"columns": {}, "primary_keys": []})
        item["columns"][column] = {"data_type": data_type, "column_key": column_key}
        if column_key == "PRI":
            item["primary_keys"].append(column)

    drift: list[dict[str, Any]] = []
    tables: dict[str, Any] = {}
    for table in BUSINESS_TABLES:
        expected = metadata.get(table, {})
        observed = actual.get(table)
        expected_columns = set((expected.get("columns") or {}).keys())
        expected_keys = list((expected.get("grain") or {}).get("keys") or [])
        time_column = (expected.get("time") or {}).get("field")
        if observed is None:
            drift.append({"type": "MISSING_TABLE", "table": table})
            tables[table] = {"exists": False}
            continue
        actual_columns = set(observed["columns"])
        missing_columns = sorted(expected_columns - actual_columns)
        missing_keys = sorted(set(expected_keys) - actual_columns)
        if missing_columns:
            drift.append({"type": "MISSING_COLUMN", "table": table, "columns": missing_columns})
        if missing_keys:
            drift.append({"type": "MISSING_BUSINESS_KEY", "table": table, "columns": missing_keys})
        if time_column and time_column not in actual_columns:
            drift.append({"type": "MISSING_DATE_COLUMN", "table": table, "column": time_column})
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        row_count = int(cursor.fetchone()[0])
        expected_count = expected.get("row_count")
        if expected_count is not None and row_count != int(expected_count):
            drift.append({"type": "ROW_COUNT_DRIFT", "table": table, "metadata": int(expected_count), "actual": row_count})
        tables[table] = {
            "exists": True,
            "columns": list(observed["columns"]),
            "column_count": len(actual_columns),
            "date_column": time_column,
            "business_keys": expected_keys,
            "business_keys_present": not missing_keys,
            "primary_keys": observed["primary_keys"],
            "row_count": row_count,
            "metadata_row_count": expected_count,
        }
    report = {"db_name": config.name, "tables": tables, "schema_drift": drift, "verification_pass": not drift}
    write_json("schema_check.json", report)
    return report


def run_smoke(connection: Any) -> dict[str, Any]:
    agent, generator, manager = AgentOrchestrator(), SQLGenerator(), ExecutionManager()
    cases: list[dict[str, Any]] = []
    for case_id, scenario, query in SMOKE_CASES:
        started = perf_counter()
        item: dict[str, Any] = {"case_id": case_id, "scenario": scenario, "query": query}
        state = agent.run(query)
        item.update(agent_status=state.status.value, plan_latency_ms=state.latency_ms)
        if state.status.value != "ready":
            item.update(execution_success=False, rows_returned=0, validation_status="NOT_RUN", failure_stage="SEMANTIC_OR_PLAN")
            cases.append(item)
            break
        try:
            compile_started = perf_counter()
            artifact = generator.generate(state.query_id, state.query_plan, state.validation_result)
            item["sql_compile_latency_ms"] = round((perf_counter() - compile_started) * 1000, 3)
        except SQLGenerationError as exc:
            item.update(execution_success=False, rows_returned=0, validation_status="NOT_RUN", failure_stage="SQL_COMPILE", error_code=exc.code, error=str(exc))
            cases.append(item)
            break
        result = manager.execute(artifact, connection)
        item.update(
            execution_success=result.status == "success",
            rows_returned=len(result.rows),
            validation_status=(result.trace.result_validation or {}).get("allowed") if result.trace else False,
            execution_status=result.status,
            explain_status="PASS" if result.trace and result.trace.explain_summary else "NOT_AVAILABLE",
            latency_ms=result.trace.latency_breakdown_ms if result.trace else {},
            end_to_end_latency_ms=round((perf_counter() - started) * 1000, 3),
        )
        if result.status != "success":
            item["failure_stage"] = "REAL_DB_EXECUTION"
            item["error"] = result.trace.error if result.trace else None
        cases.append(item)
        if result.status != "success":
            break
    report = {"case_count_planned": len(SMOKE_CASES), "case_count_run": len(cases), "cases": cases, "verification_pass": len(cases) == len(SMOKE_CASES) and all(item["execution_success"] for item in cases)}
    write_json("smoke_test.json", report)
    return report


def main() -> int:
    present, missing = effective_env()
    if missing:
        payload = {
            "connection_success": False,
            "current_user": None,
            "database": os.getenv("DB_NAME") or None,
            "readonly_verification": "NOT_RUN",
            "schema_check": "NOT_RUN",
            "smoke_test": "NOT_RUN",
            "error": "Missing required environment variables: " + ", ".join(missing),
            "environment": present,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    connection = None
    try:
        config = DatabaseConfig.from_env()
        connection = create_readonly_connection(config)
        readonly = verify_readonly(connection, config)
        payload: dict[str, Any] = {
            "connection_success": True,
            "current_user": readonly["current_user"],
            "database": readonly["db_name"],
            "readonly_verification": "PASS" if readonly["verification_pass"] else "FAIL",
            "schema_check": "NOT_RUN",
            "smoke_test": "NOT_RUN",
            "error": None,
        }
        if not readonly["verification_pass"]:
            payload["error"] = "Read-only verification failed; benchmark and smoke test are blocked."
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 3
        schema = schema_reality_check(connection, config)
        payload["schema_check"] = "PASS" if schema["verification_pass"] else "FAIL"
        if not schema["verification_pass"]:
            payload["error"] = "SCHEMA_DRIFT detected; smoke test and benchmark are blocked."
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 4
        smoke = run_smoke(connection)
        payload["smoke_test"] = "PASS" if smoke["verification_pass"] else "FAIL"
        if not smoke["verification_pass"]:
            payload["error"] = "Real DB smoke test failed; benchmark is blocked."
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 5
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "connection_success": False,
            "current_user": None,
            "database": os.getenv("DB_NAME") or None,
            "readonly_verification": "NOT_RUN",
            "schema_check": "NOT_RUN",
            "smoke_test": "NOT_RUN",
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2))
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
