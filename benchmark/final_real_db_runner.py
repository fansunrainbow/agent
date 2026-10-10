from __future__ import annotations

from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any, Callable

from agent.orchestrator import AgentOrchestrator
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator

FROZEN_GOLD_SHA256 = "602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD"
RESULT_TYPES = ("scalar", "set", "grouped", "ranking", "time_series")
LATENCY_KEYS = (
    "semantic_latency_ms", "plan_latency_ms", "sql_compile_latency_ms",
    "guardrail_latency_ms", "explain_latency_ms", "db_execution_latency_ms",
    "result_validation_latency_ms", "end_to_end_latency_ms",
)


def normal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "_mapping"):
        return normal(dict(value._mapping))
    if isinstance(value, dict):
        return {str(key): normal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normal(item) for item in value]
    return value


def rows_as_dicts(rows: list[Any], columns: list[str]) -> list[dict[str, Any]]:
    return [normal(row if isinstance(row, dict) else dict(row._mapping) if hasattr(row, "_mapping") else dict(zip(columns, row))) for row in rows]


def value_equal(left: Any, right: Any, absolute: float, relative: float) -> bool:
    left, right = normal(left), normal(right)
    if not isinstance(left, bool) and not isinstance(right, bool) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), abs_tol=absolute, rel_tol=relative)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(value_equal(left[key], right[key], absolute, relative) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(value_equal(a, b, absolute, relative) for a, b in zip(left, right))
    return left == right


def unordered_equal(actual: list[dict[str, Any]], expected: list[dict[str, Any]], absolute: float, relative: float) -> bool:
    if len(actual) != len(expected):
        return False
    remaining = list(actual)
    for wanted in expected:
        index = next((i for i, row in enumerate(remaining) if value_equal(row, wanted, absolute, relative)), None)
        if index is None:
            return False
        remaining.pop(index)
    return not remaining


def identity(row: dict[str, Any]) -> str:
    for key in ("pty_id", "customer_id", "id"):
        if key in row:
            return str(row[key])
    return json.dumps(normal(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compare_result(actual: list[Any], case: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    rows = rows_as_dicts(actual, columns)
    expected = normal(case["gold_result"])
    kind = case["expected_result_type"]
    tolerance = case.get("numeric_tolerance") or {}
    absolute, relative = float(tolerance.get("absolute", .01)), float(tolerance.get("relative", 1e-9))
    detail: dict[str, Any] = {"type": kind, "correct": False}
    if kind == "scalar":
        observed = next(iter(rows[0].values())) if rows else None
        correct = value_equal(observed, expected, absolute, relative)
        detail.update(expected=expected, actual=observed, absolute_tolerance=absolute, relative_tolerance=relative, correct=correct)
        if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
            error = abs(float(observed) - float(expected))
            detail.update(absolute_error=error, relative_error=error / abs(float(expected)) if float(expected) else (0.0 if error == 0 else None))
        return detail
    if kind == "set":
        actual_ids, expected_ids = {identity(row) for row in rows}, {identity(row) for row in expected}
        common = actual_ids & expected_ids
        precision = len(common) / len(actual_ids) if actual_ids else (1.0 if not expected_ids else 0.0)
        recall = len(common) / len(expected_ids) if expected_ids else (1.0 if not actual_ids else 0.0)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        detail.update(identity_key="pty_id when present, otherwise full row", expected_count=len(expected_ids), actual_count=len(actual_ids), precision=precision, recall=recall, f1=f1, correct=math.isclose(f1, 1.0))
        return detail
    if kind in {"grouped", "time_series"}:
        detail.update(expected_count=len(expected), actual_count=len(rows), order_ignored=True, correct=unordered_equal(rows, expected, absolute, relative))
        return detail
    if kind == "ranking":
        actual_ids, expected_ids = [identity(row) for row in rows], [identity(row) for row in expected]
        exact = actual_ids == expected_ids
        overlap = len(set(actual_ids) & set(expected_ids)) / len(expected_ids) if expected_ids else (1.0 if not actual_ids else 0.0)
        detail.update(k=len(expected_ids), expected_ids=expected_ids, actual_ids=actual_ids, exact_top_k=exact, overlap_at_k=overlap, correct=exact)
        return detail
    raise ValueError(f"unknown result type: {kind}")


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(math.ceil(ratio * len(ordered)) - 1, len(ordered) - 1)]


def latency_stats(values: list[float]) -> dict[str, Any]:
    return {"count": len(values), "avg": mean(values) if values else None, "p50": median(values) if values else None, "p95": percentile(values, .95), "max": max(values) if values else None}


def frozen_integrity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return {"expected_sha256": FROZEN_GOLD_SHA256, "actual_sha256": digest, "passed": digest == FROZEN_GOLD_SHA256}


class FinalRealDBBenchmarkRunner:
    def __init__(self, connection: Any):
        self.connection, self.agent, self.generator, self.manager = connection, AgentOrchestrator(), SQLGenerator(), ExecutionManager()

    @staticmethod
    def load(path: Path) -> list[dict[str, Any]]:
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(cases) != 40:
            raise ValueError(f"Frozen benchmark requires 40 cases; found {len(cases)}")
        for case in cases:
            if case.get("review_status") != "reviewed":
                raise ValueError(f"{case.get('case_id')} is not reviewed")
            if case.get("gold_source") == "agent_generated" or case.get("expected_result_type") not in RESULT_TYPES:
                raise ValueError(f"{case.get('case_id')} has invalid Gold metadata")
        return cases

    def timed_agent_run(self, query: str) -> tuple[Any, dict[str, float]]:
        timings: dict[str, float] = {}
        targets = [
            (self.agent.retriever, "retrieve", "semantic_retrieve"),
            (self.agent.concept_expander, "expand", "semantic_concept"),
            (self.agent.entity_resolver, "resolve", "semantic_entity"),
            (self.agent.router, "route", "semantic_route"),
            (self.agent.planner, "plan", "plan"),
        ]
        originals: list[tuple[Any, str, Callable[..., Any]]] = []
        for owner, name, key in targets:
            original = getattr(owner, name)
            originals.append((owner, name, original))
            def wrapped(*args: Any, __original: Callable[..., Any] = original, __key: str = key, **kwargs: Any) -> Any:
                started = perf_counter()
                try:
                    return __original(*args, **kwargs)
                finally:
                    timings[__key] = timings.get(__key, 0.0) + (perf_counter() - started) * 1000
            setattr(owner, name, wrapped)
        try:
            state = self.agent.run(query)
        finally:
            for owner, name, original in originals:
                setattr(owner, name, original)
        semantic = sum(value for key, value in timings.items() if key.startswith("semantic_"))
        return state, {"semantic_latency_ms": round(semantic, 3), "plan_latency_ms": round(timings.get("plan", 0.0), 3)}

    @staticmethod
    def semantic_failure(state: Any) -> tuple[str, str]:
        validation = state.validation_result or {}
        codes = [item.get("code", "") for item in validation.get("errors", [])]
        statuses = [str(getattr(item, "status", "")) for item in state.grounded_conditions]
        if any("ENTITY" in code for code in codes) or any(value in {"ambiguous", "not_found"} for value in statuses):
            return "ENTITY_RESOLUTION_ERROR", json.dumps(codes, ensure_ascii=False)
        if any("TIME" in code or "DATE" in code for code in codes):
            return "TIME_PARSE_ERROR", json.dumps(codes, ensure_ascii=False)
        if state.query_plan is not None and validation and not validation.get("valid", False):
            return "PLAN_ERROR", json.dumps(codes, ensure_ascii=False)
        clarification = state.clarification.model_dump(mode="json") if state.clarification else {"status": state.status.value}
        return "SEMANTIC_ERROR", json.dumps(clarification, ensure_ascii=False)

    def run(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for case in cases:
            started = perf_counter()
            row: dict[str, Any] = {
                "case_id": case["case_id"], "difficulty": case["difficulty"], "query": case["query"],
                "comparison_type": case["expected_result_type"], "semantic_status": "NOT_RUN", "query_plan": None,
                "generated_sql": None, "params": {}, "guardrail_status": "NOT_RUN", "explain_summary": None,
                "db_execution_status": "NOT_RUN", "result_validation_status": "NOT_RUN", "sql_execution_success": False,
                "gold_result": normal(case["gold_result"]), "actual_result": None, "gold_comparison": None,
                "result_equivalent": False, "final_correct": False, "failure_type": None, "failure_reason": None,
            }
            try:
                state, times = self.timed_agent_run(case["query"])
                row.update(times, semantic_status=state.status.value, query_plan=normal(state.query_plan), plan_validation=normal(state.validation_result), agent_trace=normal([item.model_dump(mode="json") for item in state.trace]))
                if state.status.value != "ready":
                    row["failure_type"], row["failure_reason"] = self.semantic_failure(state)
                    continue
                compile_started = perf_counter()
                try:
                    artifact = self.generator.generate(state.query_id, state.query_plan, state.validation_result)
                except SQLGenerationError as exc:
                    row.update(sql_compile_latency_ms=round((perf_counter() - compile_started) * 1000, 3), failure_type="SQL_COMPILE_ERROR", failure_reason=f"{exc.code}: {exc}")
                    continue
                row.update(sql_compile_latency_ms=round((perf_counter() - compile_started) * 1000, 3), generated_sql=artifact.sql, params=normal(artifact.params))
                result = self.manager.execute(artifact, self.connection)
                trace = result.trace
                row["db_execution_status"] = result.status
                if trace:
                    validation, rv, timing = trace.validation or {}, trace.result_validation, trace.latency_breakdown_ms or {}
                    row.update(
                        guardrail_status="PASS" if validation.get("allowed") else "BLOCK", guardrail_result=normal(validation),
                        explain_summary=normal(trace.explain_summary), result_validation=normal(rv),
                        result_validation_status="PASS" if rv and rv.get("allowed") else "BLOCK" if rv else "NOT_RUN",
                        guardrail_latency_ms=timing.get("guardrail"), explain_latency_ms=timing.get("explain"),
                        db_execution_latency_ms=timing.get("db_execution"), result_validation_latency_ms=timing.get("result_validation"),
                    )
                if result.status != "success":
                    error, code = trace.error if trace else None, str(((trace.error if trace else None) or {}).get("code", ""))
                    failure = "TIMEOUT" if "TIMEOUT" in code else "COST_BLOCK" if code == "DB_EXPLAIN_COST_EXCEEDED" else "GUARDRAIL_BLOCK" if result.status == "blocked" else "RESULT_VALIDATION_ERROR" if result.status == "result_blocked" else "DB_EXECUTION_ERROR"
                    row.update(failure_type=failure, failure_reason=json.dumps(error or {"status": result.status}, ensure_ascii=False))
                    continue
                row["sql_execution_success"] = True
                row["actual_result"] = rows_as_dicts(result.rows, result.columns)
                comparison = compare_result(result.rows, case, result.columns)
                correct = bool(comparison["correct"])
                row.update(gold_comparison=comparison, result_equivalent=correct, final_correct=correct)
                if not correct:
                    row.update(failure_type="RANKING_MISMATCH" if case["expected_result_type"] == "ranking" else "RESULT_MISMATCH", failure_reason=json.dumps(comparison, ensure_ascii=False))
            except Exception as exc:
                row.update(failure_type="GOLD_ERROR" if isinstance(exc, (KeyError, ValueError)) else "DB_EXECUTION_ERROR", failure_reason=f"{type(exc).__name__}: {exc}")
            finally:
                row["end_to_end_latency_ms"] = round((perf_counter() - started) * 1000, 3)
                output.append(row)
        return output

    @staticmethod
    def summarize(results: list[dict[str, Any]], integrity: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        total, executed, correct = len(results), sum(bool(x["sql_execution_success"]) for x in results), sum(bool(x["final_correct"]) for x in results)
        accuracy: dict[str, Any] = {}
        for kind in RESULT_TYPES:
            subset = [x for x in results if x["comparison_type"] == kind]
            matched = sum(bool(x["final_correct"]) for x in subset)
            accuracy[kind] = {"correct": matched, "total": len(subset), "accuracy": matched / len(subset) if subset else None}
        latency: dict[str, Any] = {"by_difficulty": {}, "all": {}}
        for difficulty in ("simple", "medium", "complex"):
            subset = [x for x in results if x["difficulty"] == difficulty]
            latency["by_difficulty"][difficulty] = {key: latency_stats([float(x[key]) for x in subset if isinstance(x.get(key), (int, float))]) for key in LATENCY_KEYS}
        latency["all"] = {key: latency_stats([float(x[key]) for x in results if isinstance(x.get(key), (int, float))]) for key in LATENCY_KEYS}
        maxima = {d: latency["by_difficulty"][d]["end_to_end_latency_ms"]["max"] for d in ("simple", "medium", "complex")}
        failures = Counter(x["failure_type"] for x in results if x.get("failure_type"))
        report = {
            "status": "COMPLETED", "real_db": True, "gold_integrity": integrity, "case_count": total,
            "difficulty_distribution": dict(Counter(x["difficulty"] for x in results)),
            "sql_execution_success": {"successful": executed, "total": total, "rate": executed / total if total else 0.0},
            "result_accuracy": accuracy,
            "result_equivalence": {"equivalent": correct, "total": total, "rate": correct / total if total else 0.0},
            "final_execution_accuracy": {"correct_cases": correct, "total_cases": total, "accuracy": correct / total if total else 0.0},
            "natural_language_final_execution_accuracy_target": "PASS" if total and correct / total >= .9 else "FAIL",
            "minute_level_requirement": "PASS" if all(value is not None and value < 60000 for value in maxima.values()) else "FAIL",
            "difficulty_max_end_to_end_ms": maxima, "failure_count": total - correct, "failure_distribution": dict(sorted(failures.items())),
        }
        return report, latency

    @staticmethod
    def write(results: list[dict[str, Any]], output_dir: Path, integrity: dict[str, Any]) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        report, latency = FinalRealDBBenchmarkRunner.summarize(results, integrity)
        failures = [x for x in results if not x["final_correct"]]
        (output_dir / "final_real_db_benchmark_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "final_real_db_failure_cases.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in failures), encoding="utf-8")
        (output_dir / "final_real_db_result_comparison.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in results), encoding="utf-8")
        (output_dir / "final_real_db_latency_report.json").write_text(json.dumps(latency, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# Final Real DB Benchmark Report", "", f"- Gold integrity: {'PASS' if integrity['passed'] else 'FAIL'} (`{integrity['actual_sha256']}`)", f"- Cases: {report['case_count']} ({report['difficulty_distribution']})", f"- SQL execution success: {report['sql_execution_success']['successful']}/{report['sql_execution_success']['total']} ({report['sql_execution_success']['rate']:.2%})", f"- Result equivalence: {report['result_equivalence']['equivalent']}/{report['result_equivalence']['total']} ({report['result_equivalence']['rate']:.2%})", f"- Final execution accuracy: {report['final_execution_accuracy']['correct_cases']}/{report['final_execution_accuracy']['total_cases']} ({report['final_execution_accuracy']['accuracy']:.2%})", f"- >=90% target: {report['natural_language_final_execution_accuracy_target']}", f"- Minute-level requirement: {report['minute_level_requirement']}", f"- Failures: {report['failure_count']} {report['failure_distribution']}", "", "## Accuracy by result type", "", "| Type | Correct | Total | Accuracy |", "|---|---:|---:|---:|"]
        for kind in RESULT_TYPES:
            value = report["result_accuracy"][kind]
            rendered_accuracy = "N/A" if value["accuracy"] is None else f"{value['accuracy']:.2%}"
            lines.append(f"| {kind} | {value['correct']} | {value['total']} | {rendered_accuracy} |")
        lines += ["", "## Failure analysis", ""]
        if failures:
            for kind, count in report["failure_distribution"].items():
                lines.append(f"- **{kind}** ({count}): {', '.join(x['case_id'] for x in failures if x['failure_type'] == kind)}")
        else:
            lines.append("- No failed cases.")
        lines += ["", "No production fixes were applied during or after this first frozen run.", ""]
        (output_dir / "final_real_db_benchmark_report.md").write_text("\n".join(lines), encoding="utf-8")
        compatibility = {"status": "COMPLETED", "real_db": True, "case_count": report["case_count"], "sql_execution_success_rate": report["sql_execution_success"]["rate"], "result_accuracy": report["result_equivalence"]["rate"], "result_equivalence": report["result_equivalence"]["rate"], "final_execution_accuracy": report["final_execution_accuracy"]["accuracy"]}
        (output_dir / "real_db_benchmark_report.json").write_text(json.dumps(compatibility, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
