from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any

from .models import GuardIssue, SQLArtifact
from .result_validator import ResultValidator
from .result_normalizer import ResultNormalizer
from .sql_validator import SQLValidator


@dataclass
class ExecutionTrace:
    query_id: str
    query_plan: dict[str, Any]
    status: str
    validation: dict[str, Any]
    sql: str
    parameter_names: list[str]
    attempts: int
    elapsed_ms: float
    explain_summary: dict[str, Any] | None = None
    latency_breakdown_ms: dict[str, float] = field(default_factory=dict)
    result_validation: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    status: str
    rows: list[Any] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    trace: ExecutionTrace | None = None


class ExecutionManager:
    """Final fail-closed boundary. A DB-API connection must be injected explicitly."""

    def __init__(self, validator: SQLValidator | None = None) -> None:
        self.validator = validator or SQLValidator()
        self.result_validator = ResultValidator(self.validator.schema.catalog)

    def dry_run(self, artifact: SQLArtifact) -> ExecutionResult:
        started = perf_counter()
        report = self.validator.validate(artifact)
        trace = ExecutionTrace(
            query_id=artifact.query_id, query_plan=artifact.query_plan, status="validated" if report.allowed else "blocked",
            validation=report.to_dict(), sql=artifact.sql, parameter_names=sorted(artifact.params),
            attempts=0, elapsed_ms=round((perf_counter() - started) * 1000, 3),
        )
        return ExecutionResult(trace.status, trace=trace)

    def execute(self, artifact: SQLArtifact, connection: Any) -> ExecutionResult:
        started = perf_counter()
        validate_started = perf_counter()
        report = self.validator.validate(artifact)
        guardrail_ms = round((perf_counter() - validate_started) * 1000, 3)
        if not report.allowed:
            trace = ExecutionTrace(query_id=artifact.query_id, query_plan=artifact.query_plan, status="blocked", validation=report.to_dict(), sql=artifact.sql, parameter_names=sorted(artifact.params), attempts=0, elapsed_ms=round((perf_counter() - started) * 1000, 3), latency_breakdown_ms={"guardrail": guardrail_ms})
            return ExecutionResult("blocked", trace=trace)
        try:
            self._require_read_only(connection)
            timeout = int(self.validator.cost.policy["max_execution_time_seconds"])
            timeout_setter = getattr(connection, "set_statement_timeout", None)
            if callable(timeout_setter):
                timeout_setter(timeout)
            explain_started = perf_counter()
            explain_fn = getattr(connection, "explain", None)
            explain_summary = explain_fn(artifact.sql, artifact.params) if callable(explain_fn) else {"status": "not_available"}
            explain_ms = round((perf_counter() - explain_started) * 1000, 3)
            db_estimate = int(explain_summary.get("estimated_rows", 0) or 0)
            estimate_limit = int(self.validator.cost.policy["max_estimated_scan_rows"])
            if db_estimate > estimate_limit:
                blocked_report = report.to_dict()
                blocked_report["db_explain_estimate"] = explain_summary
                trace = ExecutionTrace(
                    query_id=artifact.query_id, query_plan=artifact.query_plan, status="blocked",
                    validation=blocked_report, sql=artifact.sql, parameter_names=sorted(artifact.params),
                    attempts=0, elapsed_ms=round((perf_counter() - started) * 1000, 3),
                    explain_summary=explain_summary,
                    latency_breakdown_ms={"guardrail": guardrail_ms, "explain": explain_ms},
                    error={"code": "DB_EXPLAIN_COST_EXCEEDED", "estimated_rows": db_estimate, "limit": estimate_limit},
                )
                return ExecutionResult("blocked", trace=trace)
            execute_started = perf_counter()
            cursor = connection.cursor()
            cursor.execute(artifact.sql, artifact.params)
            maximum = int(self.validator.cost.policy["max_result_rows"])
            rows = list(cursor.fetchmany(maximum + 1))
            columns = [item[0] for item in (cursor.description or [])]
            execution_ms = round((perf_counter() - execute_started) * 1000, 3)
            result_started = perf_counter()
            normalized_rows = ResultNormalizer.normalize(rows, columns, artifact)
            result_check = self.result_validator.check(normalized_rows, artifact, columns)
            result_validation_ms = round((perf_counter() - result_started) * 1000, 3)
            execution_seconds = perf_counter() - started
            if execution_seconds > timeout:
                result_check.issues.append(GuardIssue("COST_LIMIT", "执行时间超过策略上限。", evidence={"seconds": round(execution_seconds, 3), "limit": timeout}))
                result_check.allowed = False
            status = "success" if result_check.allowed else "result_blocked"
            trace = ExecutionTrace(
                query_id=artifact.query_id, query_plan=artifact.query_plan, status=status,
                validation=report.to_dict(), sql=artifact.sql, parameter_names=sorted(artifact.params), attempts=1,
                elapsed_ms=round((perf_counter() - started) * 1000, 3), result_validation=result_check.to_dict(),
                explain_summary=explain_summary,
                latency_breakdown_ms={"guardrail": guardrail_ms, "explain": explain_ms, "db_execution": execution_ms, "result_validation": result_validation_ms},
            )
            return ExecutionResult(status, normalized_rows if result_check.allowed else [], columns, trace)
        except Exception as exc:
            error = self.classify_error(exc)
            trace = ExecutionTrace(
                query_id=artifact.query_id, query_plan=artifact.query_plan, status="execution_error",
                validation=report.to_dict(), sql=artifact.sql, parameter_names=sorted(artifact.params), attempts=1,
                elapsed_ms=round((perf_counter() - started) * 1000, 3), error=error,
                latency_breakdown_ms={"guardrail": guardrail_ms},
            )
            return ExecutionResult("execution_error", trace=trace)

    @staticmethod
    def _require_read_only(connection: Any) -> None:
        setter = getattr(connection, "set_session", None)
        if callable(setter):
            setter(readonly=True)
            return
        if getattr(connection, "read_only", False) is not True:
            raise PermissionError("数据库连接未声明 read_only=True，拒绝执行。")

    @staticmethod
    def classify_error(exc: Exception) -> dict[str, Any]:
        message = str(exc)
        lowered = message.lower()
        if "timeout" in lowered:
            code = "DB_TIMEOUT"
        elif "permission" in lowered or "read_only" in lowered:
            code = "DB_PERMISSION_DENIED"
        elif "column" in lowered or "field" in lowered:
            code = "DB_SCHEMA_MISMATCH"
        elif "syntax" in lowered:
            code = "DB_SQL_SYNTAX"
        else:
            code = "DB_EXECUTION_ERROR"
        return {
            "code": code,
            "type": type(exc).__name__,
            "message": message,
            "controlled_repair": {
                "attempted": False,
                "reason": "没有可证明保持 Query Plan 语义的确定性修复；禁止自由改写 SQL。",
                "next_step": "修复 metadata/compiler 后重新生成，并重新通过全部 Guard。",
            },
        }
