"""Interactive acceptance CLI for the existing Stage 5 Agent Core.

This script is intentionally a thin adapter: it calls AgentOrchestrator and
prints state for human inspection. It does not generate SQL or bypass the
Stage 4 validator.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import AgentOrchestrator
from agent.models import AgentState


EXIT_COMMANDS = {"exit", "quit"}


def build_output(state: AgentState) -> dict[str, Any]:
    """Select the complete acceptance view from one AgentState."""
    return {
        "user_query": state.user_query,
        "final_status": state.status.value,
        "grounded_conditions": [item.model_dump(mode="json") for item in state.grounded_conditions],
        "retrieved_metrics": state.retrieved_metrics,
        "retrieved_dimensions": state.retrieved_dimensions,
        "retrieved_concepts": state.retrieved_concepts,
        "resolved_entities": state.resolved_entities,
        "query_plan": state.query_plan,
        "validation_result": state.validation_result,
        "clarification": (
            state.clarification.model_dump(mode="json")
            if state.clarification is not None
            else None
        ),
        "repair_count": state.repair_count,
        "trace": [item.model_dump(mode="json") for item in state.trace],
    }


def update_conversation_context(
    context: dict[str, Any],
    state: AgentState,
) -> dict[str, Any]:
    """Carry the latest plan and safe Agent context into the next turn."""
    updated = dict(state.conversation_context)
    if state.query_plan is not None:
        updated["previous_plan"] = state.query_plan
        updated["parent_plan_id"] = state.query_id
    context.clear()
    context.update(updated)
    return context


def print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    orchestrator = AgentOrchestrator()
    conversation_context: dict[str, Any] = {}

    print("Stage 5 Agent 人工验收 CLI")
    print("请输入自然语言问题；输入 exit 或 quit 退出。")

    while True:
        try:
            user_query = input("\nagent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            return 0

        if not user_query:
            continue
        if user_query.lower() in EXIT_COMMANDS:
            print("已退出。")
            return 0

        state = orchestrator.run(user_query, conversation_context)
        print_json(build_output(state))
        update_conversation_context(conversation_context, state)


if __name__ == "__main__":
    raise SystemExit(main())
