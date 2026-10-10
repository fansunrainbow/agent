from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from agent.models import AgentState
from agent.tools import RegistryTool


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_requests: int
    ready_requests: int
    clarification_requests: int
    unsupported_requests: int
    semantic_hallucination_count: int
    semantic_hallucination_rate: float
    average_tool_calls: float
    average_latency_ms: float


def evaluate(states: list[AgentState], registry: RegistryTool | None = None) -> BenchmarkResult:
    registry = registry or RegistryTool()
    hallucinations = 0
    for state in states:
        plan = state.query_plan or {}
        invalid = False
        invalid |= any(metric not in registry.ids("metric") for metric in plan.get("metrics", []))
        invalid |= any(dimension not in registry.ids("dimension") for dimension in plan.get("dimensions", []))
        for source in state.grounding_sources:
            if source.get("type") == "concept" and source.get("id") not in registry.ids("concept"):
                invalid = True
            if source.get("type") == "entity" and source.get("id") and not source.get("source"):
                invalid = True
        hallucinations += int(invalid)

    total = len(states)
    return BenchmarkResult(
        total_requests=total,
        ready_requests=sum(state.status == "ready" for state in states),
        clarification_requests=sum(state.status == "needs_clarification" for state in states),
        unsupported_requests=sum(state.status == "unsupported" for state in states),
        semantic_hallucination_count=hallucinations,
        semantic_hallucination_rate=(hallucinations / total if total else 0.0),
        average_tool_calls=(sum(len(state.routed_tools) for state in states) / total if total else 0.0),
        average_latency_ms=(sum(state.latency_ms or 0 for state in states) / total if total else 0.0),
    )

