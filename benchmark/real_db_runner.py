from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

from agent.orchestrator import AgentOrchestrator
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator


FAILURE_TYPES = {
    "SEMANTIC_ERROR", "PLAN_ERROR", "SQL_COMPILE_ERROR", "GUARDRAIL_BLOCK",
    "DB_EXECUTION_ERROR", "RESULT_MISMATCH", "TIMEOUT", "EMPTY_RESULT_MISMATCH", "GOLD_ERROR",
}


def _normal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    return value


def equivalent(actual: list[Any], gold: Any, kind: str, columns: list[str]) -> bool:
    rows = [_normal(dict(row._mapping) if hasattr(row, "_mapping") else dict(zip(columns, row)) if not isinstance(row, dict) else row) for row in actual]
    expected = _normal(gold)
    if kind == "scalar":
        value = next(iter(rows[0].values())) if rows else None
        return value == expected
    if kind in {"set", "grouped"}:
        encode = lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
        return sorted(map(encode, rows)) == sorted(map(encode, expected))
    if kind == "ranking":
        return rows == expected
    raise ValueError(f"unknown comparison kind: {kind}")


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]


def latency_stats(values: list[float]) -> dict[str, float | None]:
    return {"avg": mean(values) if values else None, "p50": median(values) if values else None, "p95": _percentile(values, .95), "max": max(values) if values else None}


class RealDBBenchmarkRunner:
    def __init__(self, connection: Any):
        self.connection = connection
        self.agent = AgentOrchestrator()
        self.generator = SQLGenerator()
        self.manager = ExecutionManager()

    @staticmethod
    def load(path: Path) -> list[dict[str, Any]]:
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not 30 <= len(cases) <= 50:
            raise ValueError("真实执行 Benchmark 必须包含 30～50 个 case")
        for case in cases:
            if not case.get("gold_source") or case.get("gold_source") == "agent_generated":
                raise ValueError(f"{case.get('case_id')} 缺少独立 gold_source")
            if "gold_result" not in case or case.get("comparison_kind") not in {"scalar", "set", "grouped", "ranking"}:
                raise ValueError(f"{case.get('case_id')} 缺少可比较的 gold_result/comparison_kind")
        return cases

    def run(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for case in cases:
            row = {"case_id": case["case_id"], "query": case["query"], "difficulty": case["difficulty"], "gold_source": case["gold_source"]}
            started = perf_counter()
            state = self.agent.run(case["query"])
            row["plan_latency_ms"] = state.latency_ms
            if state.status.value != "ready":
                row.update(success=False, failure_type="SEMANTIC_ERROR", status=state.status.value)
                output.append(row); continue
            try:
                compile_started = perf_counter()
                artifact = self.generator.generate(state.query_id, state.query_plan, state.validation_result)
                row["sql_compile_latency_ms"] = round((perf_counter() - compile_started) * 1000, 3)
            except SQLGenerationError as exc:
                row.update(success=False, failure_type="SQL_COMPILE_ERROR", error_code=exc.code)
                output.append(row); continue
            result = self.manager.execute(artifact, self.connection)
            row.update(sql_execution_success=result.status == "success", execution_status=result.status, sql=artifact.sql, parameter_names=sorted(artifact.params))
            if result.trace:
                row.update(result.trace.latency_breakdown_ms)
                row["explain_summary"] = result.trace.explain_summary
            if result.status != "success":
                code = (result.trace.error or {}).get("code", "") if result.trace else ""
                row.update(success=False, failure_type="TIMEOUT" if "TIMEOUT" in code else "GUARDRAIL_BLOCK" if result.status == "blocked" else "DB_EXECUTION_ERROR")
            else:
                match = equivalent(result.rows, case["gold_result"], case["comparison_kind"], result.columns)
                row.update(success=match, result_equivalent=match, failure_type=None if match else ("EMPTY_RESULT_MISMATCH" if not result.rows else "RESULT_MISMATCH"), actual_result=_normal(result.rows), gold_result=case["gold_result"])
            row["end_to_end_latency_ms"] = round((perf_counter() - started) * 1000, 3)
            output.append(row)
        return output

    @staticmethod
    def write(results: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(results); executed = sum(bool(x.get("sql_execution_success")) for x in results); correct = sum(bool(x.get("success")) for x in results)
        report = {
            "status": "COMPLETED", "real_db": True, "case_count": total,
            "sql_execution_success_rate": executed / total if total else 0,
            "result_accuracy": correct / total if total else 0,
            "result_equivalence": correct / total if total else 0,
            "final_execution_accuracy": correct / total if total else 0,
            "by_difficulty": {},
        }
        for difficulty in ("simple", "medium", "complex"):
            subset = [x for x in results if x.get("difficulty") == difficulty]
            report["by_difficulty"][difficulty] = {"count": len(subset), "end_to_end_latency_ms": latency_stats([x["end_to_end_latency_ms"] for x in subset if "end_to_end_latency_ms" in x])}
        (output_dir / "real_db_benchmark_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "real_db_benchmark_report.md").write_text("# Real DB Benchmark\n\n" + "\n".join(f"- {k}: {v}" for k, v in report.items()), encoding="utf-8")
        failures = [x for x in results if not x.get("success")]
        (output_dir / "real_db_failure_cases.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False, default=str) for x in failures), encoding="utf-8")
        (output_dir / "real_db_result_comparison.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False, default=str) for x in results), encoding="utf-8")
        latency = {key: latency_stats([x[key] for x in results if key in x]) for key in ("plan_latency_ms", "sql_compile_latency_ms", "guardrail", "explain", "db_execution", "result_validation", "end_to_end_latency_ms")}
        (output_dir / "real_db_latency_report.json").write_text(json.dumps(latency, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
