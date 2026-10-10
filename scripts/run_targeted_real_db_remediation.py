from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.final_real_db_runner import FinalRealDBBenchmarkRunner, frozen_integrity
from database import DatabaseConfig, create_readonly_connection


DATASET = ROOT / "benchmark/datasets/real_db_gold.jsonl"
REPORT_DIR = ROOT / "benchmark/reports/real_db_final"
RCA_PATH = REPORT_DIR / "failure_root_causes.json"
BASELINE_PATH = REPORT_DIR / "final_real_db_result_comparison.jsonl"
OUTPUT_PATH = REPORT_DIR / "targeted_remediation_verification.json"


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cost(row: dict[str, Any]) -> int | float | None:
    summary = row.get("explain_summary") or {}
    value = summary.get("estimated_rows")
    if isinstance(value, (int, float)):
        return value
    error = row.get("failure_reason")
    if isinstance(error, str):
        try:
            error = json.loads(error)
        except json.JSONDecodeError:
            return None
    if not isinstance(error, dict):
        return None
    details = error.get("details") or {}
    if not isinstance(details, dict):
        return None
    value = details.get("estimated_rows") or details.get("estimated_scan_rows")
    return value if isinstance(value, (int, float)) else None


def main() -> int:
    integrity = frozen_integrity(DATASET)
    if not integrity["passed"]:
        raise SystemExit(f"GOLD_INTEGRITY failed: {integrity}")

    root_causes = json.loads(RCA_PATH.read_text(encoding="utf-8"))
    case_ids = [item["case_id"] for item in root_causes["cases"]]
    if len(case_ids) != 22 or len(set(case_ids)) != 22:
        raise SystemExit("Targeted remediation requires exactly the 22 original failed case IDs")

    all_cases = {item["case_id"]: item for item in jsonl(DATASET)}
    baseline = {item["case_id"]: item for item in jsonl(BASELINE_PATH)}
    selected = [all_cases[case_id] for case_id in case_ids]
    if any(case.get("review_status") != "reviewed" for case in selected):
        raise SystemExit("All targeted Frozen Gold cases must remain reviewed")

    config = DatabaseConfig.from_env()
    if config.user != "agent_readonly_user":
        raise SystemExit(f"targeted verification requires agent_readonly_user; configured user is {config.user!r}")
    connection = create_readonly_connection(config)
    capability = connection.capability_check()
    if not capability.readonly_verified:
        raise SystemExit("read-only capability check failed")
    try:
        current = FinalRealDBBenchmarkRunner(connection).run(selected)
    finally:
        connection.close()

    comparisons = []
    for row in current:
        before = baseline[row["case_id"]]
        comparisons.append({
            "case_id": row["case_id"],
            "before_correct": bool(before.get("final_correct")),
            "after_correct": bool(row.get("final_correct")),
            "before_failure_type": before.get("failure_type"),
            "after_failure_type": row.get("failure_type"),
            "before_sql_execution_success": bool(before.get("sql_execution_success")),
            "after_sql_execution_success": bool(row.get("sql_execution_success")),
            "before_estimated_rows": cost(before),
            "after_estimated_rows": cost(row),
            "generated_sql": row.get("generated_sql"),
            "params": row.get("params"),
            "gold_comparison": row.get("gold_comparison"),
            "failure_reason": row.get("failure_reason"),
            "end_to_end_latency_ms": row.get("end_to_end_latency_ms"),
        })

    report = {
        "scope": "original_22_failures_only",
        "full_frozen_benchmark_rerun": False,
        "gold_integrity": integrity,
        "readonly_verified": capability.readonly_verified,
        "case_count": len(comparisons),
        "before": {
            "correct": sum(item["before_correct"] for item in comparisons),
            "sql_execution_success": sum(item["before_sql_execution_success"] for item in comparisons),
        },
        "after": {
            "correct": sum(item["after_correct"] for item in comparisons),
            "sql_execution_success": sum(item["after_sql_execution_success"] for item in comparisons),
        },
        "remaining_failures": [item["case_id"] for item in comparisons if not item["after_correct"]],
        "cost_cases": [item for item in comparisons if item["case_id"] in {"RDB_C01", "RDB_C02", "RDB_C05"}],
        "cases": comparisons,
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("scope", "case_count", "before", "after", "remaining_failures")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
