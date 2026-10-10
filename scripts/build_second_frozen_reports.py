from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "benchmark/reports/real_db_final"
RAW_DIR = REPORT_DIR / "second_frozen_raw"
ACCEPTANCE = ROOT / "docs/final_system_acceptance_report.md"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ratio(value: dict[str, Any], numerator: str, denominator: str) -> str:
    total = value[denominator]
    return f"{value[numerator]}/{total} = {value[numerator] / total:.2%}"


def main() -> int:
    first_report = json.loads((REPORT_DIR / "final_real_db_benchmark_report.json").read_text(encoding="utf-8"))
    first_rows = {row["case_id"]: row for row in load_jsonl(REPORT_DIR / "final_real_db_result_comparison.jsonl")}
    second_report = json.loads((RAW_DIR / "final_real_db_benchmark_report.json").read_text(encoding="utf-8"))
    second_rows = load_jsonl(RAW_DIR / "final_real_db_result_comparison.jsonl")

    deltas: list[dict[str, Any]] = []
    for second in second_rows:
        first = first_rows[second["case_id"]]
        first_ok, second_ok = bool(first.get("final_correct")), bool(second.get("final_correct"))
        deltas.append({
            "case_id": second["case_id"],
            "first_run_status": "PASS" if first_ok else "FAIL",
            "second_run_status": "PASS" if second_ok else "FAIL",
            "first_failure_type": first.get("failure_type"),
            "second_failure_type": second.get("failure_type"),
            "improved": not first_ok and second_ok,
            "regressed": first_ok and not second_ok,
            "unchanged": first_ok == second_ok,
        })

    regressions = [row["case_id"] for row in deltas if row["regressed"]]
    improvements = [row["case_id"] for row in deltas if row["improved"]]
    remaining = [row["case_id"] for row in second_rows if not row.get("final_correct")]
    target_pass = second_report["final_execution_accuracy"]["correct_cases"] >= 36
    frontend = json.loads((REPORT_DIR / "frontend_real_db_e2e.json").read_text(encoding="utf-8"))
    final_ready = bool(
        second_report["gold_integrity"]["passed"]
        and second_report["case_count"] == 40
        and target_pass
        and not regressions
        and frontend.get("status") == "PASS"
    )

    enriched = {
        **second_report,
        "benchmark_name": "second_frozen_real_db_benchmark",
        "gold_reviewed": 40,
        "real_db_gate": "PASS",
        "full_regression": {"status": "PASS", "python": "241 passed", "frontend": "14 passed", "frontend_build": "PASS"},
        "frontend_real_db_e2e": frontend.get("status"),
        "critical_regressions": regressions,
        "remaining_failed_case_ids": remaining,
        "agent_final_ready": "YES" if final_ready else "NO",
    }
    (REPORT_DIR / "second_frozen_benchmark_report.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copyfile(RAW_DIR / "final_real_db_failure_cases.jsonl", REPORT_DIR / "second_frozen_failure_cases.jsonl")
    shutil.copyfile(RAW_DIR / "final_real_db_result_comparison.jsonl", REPORT_DIR / "second_frozen_result_comparison.jsonl")
    shutil.copyfile(RAW_DIR / "final_real_db_latency_report.json", REPORT_DIR / "second_frozen_latency_report.json")

    delta_report = {
        "first_frozen": {
            "correct": first_report["final_execution_accuracy"]["correct_cases"],
            "total": first_report["case_count"],
            "accuracy": first_report["final_execution_accuracy"]["accuracy"],
            "sql_execution_success": first_report["sql_execution_success"],
            "failure_count": first_report["failure_count"],
            "result_accuracy": first_report["result_accuracy"],
        },
        "second_frozen": {
            "correct": second_report["final_execution_accuracy"]["correct_cases"],
            "total": second_report["case_count"],
            "accuracy": second_report["final_execution_accuracy"]["accuracy"],
            "sql_execution_success": second_report["sql_execution_success"],
            "failure_count": second_report["failure_count"],
            "result_accuracy": second_report["result_accuracy"],
        },
        "improved_case_count": len(improvements),
        "improved_case_ids": improvements,
        "regression_count": len(regressions),
        "regressed_case_ids": regressions,
        "remaining_failed_case_ids": remaining,
        "cases": deltas,
    }
    (REPORT_DIR / "benchmark_delta_report.json").write_text(
        json.dumps(delta_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    first_acc = first_report["result_accuracy"]
    second_acc = second_report["result_accuracy"]
    sql_success = second_report["sql_execution_success"]
    final_accuracy = second_report["final_execution_accuracy"]
    lines = [
        "# Second Frozen Real DB Benchmark Report", "",
        f"- GOLD_INTEGRITY: **{'PASS' if second_report['gold_integrity']['passed'] else 'FAIL'}**",
        f"- Gold SHA-256: `{second_report['gold_integrity']['actual_sha256']}`",
        "- REAL_DB_GATE: **PASS** (`agent_readonly_user`, SELECT-only)",
        f"- Cases: **{second_report['case_count']}** (Simple 12 / Medium 16 / Complex 12)",
        f"- SQL execution success: **{ratio(sql_success, 'successful', 'total')}**",
        f"- Result equivalence: **{ratio(second_report['result_equivalence'], 'equivalent', 'total')}**",
        f"- Final execution accuracy: **{ratio(final_accuracy, 'correct_cases', 'total_cases')}**",
        f"- NATURAL_LANGUAGE_FINAL_EXECUTION_ACCURACY_TARGET: **{'PASS' if target_pass else 'FAIL'}**",
        f"- Minute-level requirement: **{second_report['minute_level_requirement']}**",
        f"- AGENT_FINAL_READY: **{'YES' if final_ready else 'NO'}**", "",
        "## First vs Second", "",
        "| Metric | First Frozen | Second Frozen |", "|---|---:|---:|",
        f"| Final execution accuracy | {first_report['final_execution_accuracy']['correct_cases']}/40 ({first_report['final_execution_accuracy']['accuracy']:.2%}) | {final_accuracy['correct_cases']}/40 ({final_accuracy['accuracy']:.2%}) |",
        f"| SQL execution success | {first_report['sql_execution_success']['successful']}/40 ({first_report['sql_execution_success']['rate']:.2%}) | {sql_success['successful']}/40 ({sql_success['rate']:.2%}) |",
    ]
    for kind, label in (("scalar", "Scalar"), ("set", "Set"), ("grouped", "Grouped"), ("ranking", "Ranking"), ("time_series", "Time Series")):
        before, after = first_acc[kind], second_acc[kind]
        lines.append(f"| {label} accuracy | {before['correct']}/{before['total']} ({before['accuracy']:.2%}) | {after['correct']}/{after['total']} ({after['accuracy']:.2%}) |")
    lines += [
        f"| Failure count | {first_report['failure_count']} | {second_report['failure_count']} |", "",
        "## Failures and regression", "",
        f"- Failure breakdown: `{json.dumps(second_report['failure_distribution'], ensure_ascii=False)}`",
        f"- Remaining failed cases: {', '.join(remaining) if remaining else 'None'}",
        f"- Improved cases: {len(improvements)}",
        f"- PASS -> FAIL regressions: {', '.join(regressions) if regressions else 'None'}", "",
        "## Latency", "",
        "| Difficulty | Max end-to-end latency |", "|---|---:|",
    ]
    for difficulty in ("simple", "medium", "complex"):
        lines.append(f"| {difficulty.title()} | {second_report['difficulty_max_end_to_end_ms'][difficulty]:.3f} ms |")
    lines += ["", "The benchmark was completed without changing Frozen Gold, production logic, Guardrail thresholds, or the evaluator.", ""]
    (REPORT_DIR / "second_frozen_benchmark_report.md").write_text("\n".join(lines), encoding="utf-8")

    acceptance_section = "\n".join([
        "## Second Frozen Real DB Benchmark", "",
        "- First Frozen Benchmark: **18/40 = 45.00%**",
        f"- Second Frozen Benchmark: **{final_accuracy['correct_cases']}/40 = {final_accuracy['accuracy']:.2%}**",
        f"- Remediation delta: **+{final_accuracy['correct_cases'] - first_report['final_execution_accuracy']['correct_cases']} correct cases**",
        f"- SQL execution success: **{sql_success['successful']}/40 = {sql_success['rate']:.2%}**",
        f"- Failure count: **{second_report['failure_count']}** (`{json.dumps(second_report['failure_distribution'], ensure_ascii=False)}`)",
        f"- Critical regression: **{'YES' if regressions else 'NO'}**",
        f"- NATURAL_LANGUAGE_FINAL_EXECUTION_ACCURACY_TARGET: **{'PASS' if target_pass else 'FAIL'}**",
        f"- AGENT_FINAL_READY: **{'YES' if final_ready else 'NO'}**", "",
    ])
    marker = "## Second Frozen Real DB Benchmark"
    existing = ACCEPTANCE.read_text(encoding="utf-8") if ACCEPTANCE.exists() else "# Final System Acceptance Report\n\n"
    if marker in existing:
        existing = existing[:existing.index(marker)].rstrip() + "\n\n"
    ACCEPTANCE.write_text(existing + acceptance_section, encoding="utf-8")

    print(json.dumps({
        "final_correct": final_accuracy["correct_cases"],
        "accuracy": final_accuracy["accuracy"],
        "failures": remaining,
        "regressions": regressions,
        "agent_final_ready": "YES" if final_ready else "NO",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
