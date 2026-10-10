from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.orchestrator import AgentOrchestrator
from database import DatabaseConfig, create_readonly_connection
from database.privacy import safe_records
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Natural language -> guarded MySQL read-only execution")
    parser.add_argument("query")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="compile and validate only (default)")
    mode.add_argument("--execute", action="store_true", help="execute against configured read-only MySQL")
    args = parser.parse_args()

    total_started = perf_counter()
    plan_started = perf_counter()
    state = AgentOrchestrator().run(args.query)
    plan_ms = round((perf_counter() - plan_started) * 1000, 3)
    payload: dict = {
        "query": args.query, "mode": "REAL_DB" if args.execute else "DRY_RUN",
        "agent_status": state.status.value, "query_plan": state.query_plan,
        "latency_ms": {"plan": plan_ms},
    }
    if state.status.value != "ready":
        payload["clarification"] = state.clarification.model_dump(mode="json") if state.clarification else None
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 2
    try:
        compile_started = perf_counter()
        artifact = SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)
        payload["latency_ms"]["sql_compile"] = round((perf_counter() - compile_started) * 1000, 3)
        payload.update({"sql": artifact.sql, "params": artifact.params})
        manager = ExecutionManager()
        if args.execute:
            connection = create_readonly_connection(DatabaseConfig.from_env())
            capability = connection.capability_check()
            payload["database_capability"] = capability.to_dict()
            if not capability.readonly_verified:
                payload["execution_status"] = "blocked"
                payload["error"] = "数据库账号未通过只读能力检查"
                print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
                return 3
            result = manager.execute(artifact, connection)
            payload.update({
                "guardrail": result.trace.validation, "explain_summary": result.trace.explain_summary,
                "execution_status": result.status, "result": safe_records(result.rows, result.columns),
                "result_validation": result.trace.result_validation,
            })
            payload["latency_ms"].update(result.trace.latency_breakdown_ms)
            connection.close()
        else:
            result = manager.dry_run(artifact)
            payload.update({"guardrail": result.trace.validation, "execution_status": "dry_run_validated" if result.status == "validated" else result.status})
        payload["latency_ms"]["end_to_end"] = round((perf_counter() - total_started) * 1000, 3)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0 if result.status in {"success", "validated"} else 4
    except (SQLGenerationError, RuntimeError) as exc:
        payload.update({"execution_status": "blocked", "error": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
