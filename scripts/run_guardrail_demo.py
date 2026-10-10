from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.orchestrator import AgentOrchestrator
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 5 -> Stage 6 deterministic SQL dry-run")
    parser.add_argument("query", nargs="?", help="自然语言问题；省略后进入循环模式")
    args = parser.parse_args()
    orchestrator = AgentOrchestrator()
    generator = SQLGenerator()
    manager = ExecutionManager()
    context: dict = {}
    while True:
        query = args.query if args.query is not None else input("query> ").strip()
        if query.lower() in {"exit", "quit"}:
            return 0
        state = orchestrator.run(query, context)
        payload = {"agent_status": state.status.value, "query_plan": state.query_plan, "validation_result": state.validation_result}
        if state.status.value == "ready":
            try:
                artifact = generator.generate(state.query_id, state.query_plan, state.validation_result)
                dry_run = manager.dry_run(artifact)
                payload.update({"sql": artifact.sql, "params": artifact.params, "guardrail": dry_run.trace.to_dict()})
            except SQLGenerationError as exc:
                payload["guardrail"] = {"status": "blocked", "code": exc.code, "message": str(exc), "evidence": exc.evidence}
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        if state.query_plan:
            context["previous_plan"] = state.query_plan
            context["parent_query_id"] = state.query_id
        if args.query is not None:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
