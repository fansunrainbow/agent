from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent.models import AgentState, GroundedCondition
from agent.services.metadata_store import MetadataStore


class ConceptExpander:
    """Expand registered concepts into executable grounded conditions before planning."""

    NEGATION_MARKERS = ("没有", "未", "不含", "不包括", "排除", "不是", "非")

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.expansions = self.store.yaml("concept_expansions.yaml").get("expansions", {})
        self.dictionary = self.store.yaml("business_dictionary.yaml").get("dictionary", {})
        self.dimensions = self.store.yaml("dimensions.yaml").get("dimensions", {})
        self.operators = self.store.yaml("operator_registry.yaml").get("operators", {})
        self.relation_targets = (
            self.store.yaml("agent_language.yaml")
            .get("entity_mentions", {}).get("product", {}).get("relation_targets", {})
        )

    @staticmethod
    def _values(value: Any) -> list[Any]:
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _negate(operator: str) -> str:
        return {"eq": "neq", "in": "not_in", "neq": "eq", "not_in": "in"}.get(operator, operator)

    def _is_negated(self, query: str, surface: str) -> bool:
        position = query.find(surface)
        prefix = query[max(0, position - 8):position] if position >= 0 else ""
        return any(marker in prefix for marker in self.NEGATION_MARKERS)

    def _validate(self, concept_id: str, expansion: dict[str, Any]) -> str | None:
        if concept_id not in self.dictionary:
            return f"业务概念 {concept_id} 未在 Business Dictionary 注册。"
        if not expansion.get("enabled"):
            return "Concept expansion 未启用。"
        if expansion.get("concept_id") != concept_id:
            return "Concept expansion 的 concept_id 与注册键不一致。"
        if expansion.get("target_type") != "dimension_filter":
            return "Concept expansion 目标类型不受支持。"
        dimension_id = expansion.get("target_dimension")
        dimension = self.dimensions.get(dimension_id)
        if not dimension:
            return f"目标维度 {dimension_id} 未注册。"
        operator = expansion.get("operator")
        if operator not in self.operators:
            return f"操作符 {operator} 未注册。"
        source = expansion.get("source") or {}
        if (
            source.get("table") != dimension.get("source_table")
            or source.get("field") != dimension.get("source_field")
        ):
            return "Expansion source 与 Dimension Registry 不一致。"
        actual_values = {
            row.get(source["field"])
            for row in self.store.csv_rows(source["table"])
            if row.get(source["field"])
        }
        missing = [value for value in self._values(expansion.get("canonical_value")) if value not in actual_values]
        if missing:
            return f"Canonical value 不存在于真实数据快照: {missing}"
        value_type = self.operators[operator].get("value_type")
        if value_type == "list" and not isinstance(expansion.get("canonical_value"), list):
            return "集合操作符要求 canonical_value 为列表。"
        if value_type == "scalar" and isinstance(expansion.get("canonical_value"), (list, dict)):
            return "标量操作符要求 canonical_value 为标量。"
        return None

    def _matching_expansion(self, condition: GroundedCondition) -> tuple[str, dict[str, Any]] | None:
        if condition.semantic_type == "concept" and condition.target:
            expansion = self.expansions.get(condition.target)
            return (condition.target, expansion) if expansion else None
        if condition.semantic_type != "dimension" or condition.target is None:
            return None
        matches = []
        for concept_id, expansion in self.expansions.items():
            if not expansion.get("enabled") or expansion.get("target_dimension") != condition.target:
                continue
            definition = self.dictionary.get(concept_id, {})
            accepted = {
                str(expansion.get("canonical_value")),
                *(str(value) for value in (definition.get("values") or definition.get("value_mapping") or [])),
            }
            if str(condition.value) in accepted:
                matches.append((concept_id, expansion))
        return matches[0] if len(matches) == 1 else None

    def expand(self, state: AgentState) -> AgentState:
        output: list[GroundedCondition] = []
        provenance: list[dict[str, Any]] = []
        for condition in state.grounded_conditions:
            matched = self._matching_expansion(condition)
            if condition.status != "resolved" or not matched:
                output.append(condition)
                continue
            concept_id, expansion = matched
            error = self._validate(concept_id, expansion)
            if error:
                failed = condition.model_copy(deep=True)
                failed.status = "unsupported"
                failed.reason = error
                failed.question = "该业务概念的执行映射无效，请修复 Concept Expansion Registry。"
                output.append(failed)
                provenance.append({"concept_id": concept_id, "status": "rejected", "reason": error})
                continue
            operator = expansion["operator"]
            if condition.operator in {"neq", "not_in"} or self._is_negated(state.user_query, condition.original_surface):
                operator = self._negate(operator)
            expanded = GroundedCondition(
                condition_id=condition.condition_id,
                original_surface=condition.original_surface,
                semantic_type="dimension",
                target=expansion["target_dimension"],
                operator=operator,
                value=deepcopy(expansion["canonical_value"]),
                source=self.store.source("concept_expansions.yaml"),
                confidence=condition.confidence,
                status="resolved",
                scope=condition.scope,
                patch_action=condition.patch_action,
            )
            output.append(expanded)
            provenance.append({
                "concept_id": concept_id,
                "original_surface": condition.original_surface,
                "target_type": expansion["target_type"],
                "target_dimension": expansion["target_dimension"],
                "operator": operator,
                "canonical_value": deepcopy(expansion["canonical_value"]),
                "source": self.store.source("concept_expansions.yaml"),
                "version": expansion["version"],
                "status": "expanded",
            })
            has_metric = any(
                item.status == "resolved" and item.semantic_type == "metric"
                for item in state.grounded_conditions
            )
            relation_target = None if has_metric else next(
                (target for marker, target in self.relation_targets.items() if marker in state.user_query),
                None,
            )
            if relation_target:
                relation_negated = self._is_negated(state.user_query, condition.original_surface)
                if relation_negated:
                    expanded.operator = expansion["operator"]
                    provenance[-1]["operator"] = expansion["operator"]
                output.append(GroundedCondition(
                    condition_id="pending",
                    original_surface=condition.original_surface,
                    semantic_type="entity",
                    target=relation_target,
                    operator="not_exists" if relation_negated else "exists",
                    value=None,
                    source=self.store.source("agent_language.yaml"),
                    confidence=condition.confidence,
                    status="resolved",
                    patch_action=condition.patch_action,
                ))
                provenance[-1]["relation_scope"] = relation_target
        for index, condition in enumerate(output, 1):
            condition.condition_id = f"c{index}"
        state.grounded_conditions = output
        state.add_trace(
            "expand_concepts", "success",
            source=self.store.source("concept_expansions.yaml"),
            input_summary=[item.get("concept_id") for item in provenance],
            output_summary=provenance,
        )
        return state
