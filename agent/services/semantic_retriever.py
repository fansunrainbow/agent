from __future__ import annotations

from agent.models import AgentState
from agent.services.condition_grounder import ConditionGrounder
from agent.services.metadata_store import MetadataStore
from agent.tools import DictionaryTool, DimensionTool, MetricTool


class SemanticRetriever:
    """Typed, condition-level retrieval with precision-first candidate pruning."""

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.metric_tool = MetricTool(self.store)
        self.dimension_tool = DimensionTool(self.store)
        self.dictionary_tool = DictionaryTool(self.store)
        self.grounder = ConditionGrounder(self.store)

    @staticmethod
    def _unique(items: list[dict], key: str) -> list[dict]:
        result = {}
        for item in items:
            if item.get(key) is not None:
                result[item[key]] = item
        return list(result.values())

    def retrieve(self, state: AgentState) -> AgentState:
        state.grounded_conditions = self.grounder.ground(state.user_query, state.conversation_context)
        metrics = []
        dimensions = []
        concepts = []
        dimension_values = []
        ambiguities = []

        for condition in state.grounded_conditions:
            if condition.status != "resolved":
                ambiguities.append({
                    "ambiguity_id": condition.condition_id,
                    "term": condition.original_surface,
                    "type": condition.semantic_type if condition.semantic_type in {
                        "time", "metric", "dimension", "concept", "entity",
                        "prediction_request", "suitability_request", "unsupported_attribute",
                    } else "other",
                    "options": condition.candidates,
                    "question": condition.question,
                    "reason": condition.reason,
                    "source": condition.source,
                })
                continue
            if condition.semantic_type == "metric" and condition.target:
                result = self.metric_tool.get(condition.target)
                if result.success:
                    metrics.append({
                        **result.data,
                        "matched_alias": condition.original_surface,
                        "match_type": "condition_exact",
                        "score": condition.confidence,
                        "source": result.source,
                    })
            elif condition.semantic_type == "dimension" and condition.target:
                result = self.dimension_tool.get(condition.target)
                if result.success:
                    dimensions.append({
                        **result.data,
                        "matched_alias": condition.original_surface,
                        "match_type": "condition_exact",
                        "score": condition.confidence,
                        "source": result.source,
                    })
                if condition.operator and condition.value is not None and condition.scope is None:
                    dimension_values.append({
                        "dimension_id": condition.target,
                        "value": condition.value,
                        "matched_surface": condition.original_surface,
                        "source": condition.source,
                    })
            elif condition.semantic_type == "concept" and condition.target:
                result = self.dictionary_tool.get(condition.target)
                if result.success:
                    concepts.append({
                        **result.data,
                        "matched_alias": condition.original_surface,
                        "match_type": "condition_exact",
                        "score": condition.confidence,
                        "source": result.source,
                    })

            state.grounding_sources.append({
                "type": condition.semantic_type,
                "id": condition.target,
                "surface": condition.original_surface,
                "source": condition.source,
                "confidence": condition.confidence,
            })

        state.retrieved_metrics = self._unique(metrics, "metric_id")
        state.retrieved_dimensions = self._unique(dimensions, "dimension_id")
        state.retrieved_concepts = self._unique(concepts, "concept_id")
        state.retrieved_ambiguities = ambiguities
        state.conversation_context["dimension_values"] = dimension_values

        state.add_trace(
            "retrieve_semantic_context",
            "success",
            source="typed condition grounder + metadata tools",
            input_summary=state.user_query,
            output_summary={
                "conditions": [item.model_dump(mode="json") for item in state.grounded_conditions],
                "metrics": [item.get("metric_id") for item in state.retrieved_metrics],
                "dimensions": [item.get("dimension_id") for item in state.retrieved_dimensions],
                "concepts": [item.get("concept_id") for item in state.retrieved_concepts],
                "ambiguities": [item.get("ambiguity_id") for item in state.retrieved_ambiguities],
            },
        )
        return state
