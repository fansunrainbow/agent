from __future__ import annotations

from agent.models import AgentState


class ToolRouter:
    """Route from grounded semantic types, never from product-specific branches."""

    def route(self, state: AgentState) -> list[str]:
        tools = ["registry_tool"]
        if state.retrieved_metrics:
            tools.append("metric_tool")
        if state.retrieved_dimensions:
            tools.append("dimension_tool")
        if state.retrieved_concepts or state.retrieved_ambiguities:
            tools.append("dictionary_tool")
        if state.resolved_entities:
            tools.append("entity_tool")
        if state.retrieved_metrics and state.retrieved_dimensions:
            tools.extend(["schema_tool", "join_tool"])
        return list(dict.fromkeys(tools))

