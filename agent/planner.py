from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from agent.llm import StructuredLLMProvider
from agent.models import AgentState, PlannerResult
from agent.services.context_manager import ContextManager
from agent.services.metadata_store import MetadataStore
from query_plan.models import QueryPlan


ROOT = Path(__file__).resolve().parents[1]


class Planner:
    """Build a Stage 4 plan exclusively from confirmed GroundedConditions."""

    def __init__(
        self,
        store: MetadataStore | None = None,
        provider: StructuredLLMProvider | None = None,
        context_manager: ContextManager | None = None,
    ):
        self.store = store or MetadataStore()
        self.provider = provider
        self.context_manager = context_manager or ContextManager()
        self.language = self.store.yaml("agent_language.yaml")
        self.metrics = self.store.yaml("metrics.yaml").get("metrics", {})
        self.dictionary = self.store.yaml("business_dictionary.yaml").get("dictionary", {})
        self.value_mappings = self.store.yaml("value_mappings.yaml").get("mappings", {})

    def _canonical_dimension_value(self, dimension: str, value: Any) -> Any:
        mapping = self.value_mappings.get(dimension, {})
        reverse = {str(code): semantic for semantic, code in (mapping.get("semantic_values", {}) or {}).items()}
        reverse.update({str(storage): canonical for canonical, storage in (mapping.get("values", {}) or {}).items()})
        return reverse.get(str(value), value)

    def _prompt(self) -> str:
        return (ROOT / "agent" / "prompts" / "planner.md").read_text(encoding="utf-8")

    @staticmethod
    def _unique(values: list[Any]) -> list[Any]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _grounded_ids(state: AgentState) -> dict[str, list[str]]:
        return {
            "metrics": list(dict.fromkeys(
                item.target for item in state.grounded_conditions
                if item.status == "resolved" and item.semantic_type == "metric" and item.target
            )),
            "dimensions": list(dict.fromkeys(
                item.target for item in state.grounded_conditions
                if item.status == "resolved" and item.semantic_type == "dimension" and item.target
            )),
            "concepts": list(dict.fromkeys(
                item.target for item in state.grounded_conditions
                if item.status == "resolved" and item.semantic_type == "concept" and item.target
            )),
            "entities": [
                str(candidate.get("id"))
                for entity in state.resolved_entities
                for candidate in entity.get("candidates", [])
                if candidate.get("id") is not None
            ],
        }

    def _provider_plan(self, state: AgentState) -> PlannerResult:
        schema = json.loads((ROOT / "query_plan" / "schema" / "query_plan.schema.json").read_text(encoding="utf-8"))
        payload = {
            "user_query": state.user_query,
            "conversation_context": state.conversation_context,
            "grounded_conditions": [item.model_dump(mode="json") for item in state.grounded_conditions],
            "query_plan_schema": schema,
            "allowed_intents": list(self.store.yaml("intent_registry.yaml").get("intents", {})),
        }
        try:
            plan = self.provider.generate_structured(
                system_prompt=self._prompt(), payload=payload, response_model=QueryPlan, temperature=0.0,
            )
        except Exception as exc:
            return PlannerResult(success=False, mode="provider", error_code="PLANNER_PROVIDER_ERROR", error_message=str(exc))
        return PlannerResult(success=True, plan=plan, mode="provider", grounded_ids=self._grounded_ids(state))

    def _intent(
        self,
        query: str,
        metrics: list[str],
        metric_filters: list[dict[str, Any]],
        group_by: list[str],
        order_by: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        dimensions: list[str],
    ) -> str:
        markers = self.language.get("intent_markers", {})
        if any(marker in query for marker in markers.get("trend_analysis", [])):
            return "trend_analysis"
        if "对比" in query or re.search(r"比较.{0,12}(?:和|与|vs)", query, flags=re.IGNORECASE):
            return "comparison"
        if group_by:
            return "group_analysis"
        if order_by:
            return "ranking"
        if entities and "画像" in query and any(item.get("entity_type") == "customer" for item in entities):
            return "customer_profile"
        if metric_filters:
            return "customer_selection"
        if metrics:
            return "metric_query"
        if entities:
            return "entity_lookup"
        if "客户" not in query and any(item in {"product", "product_primary_category", "product_secondary_category"} for item in dimensions):
            return "entity_lookup"
        return "customer_selection"

    @staticmethod
    def _assign_filter_ids(filters: list[dict[str, Any]]) -> None:
        counter = 0

        def assign(node: dict[str, Any]) -> None:
            nonlocal counter
            if "logic" in node:
                for child in node.get("conditions", []):
                    assign(child)
            else:
                counter += 1
                node["id"] = f"f{counter}"

        for node in filters:
            assign(node)

    def _condition_ambiguities(self, state: AgentState) -> list[dict[str, Any]]:
        return [
            {
                "term": item.original_surface,
                "type": item.semantic_type if item.semantic_type in {
                    "time", "metric", "dimension", "concept", "entity"
                } else "other",
                "reason": item.reason,
                "question": item.question,
                "candidates": item.candidates,
            }
            for item in state.grounded_conditions
            if item.status != "resolved"
        ]

    def _build_deterministic(self, state: AgentState) -> PlannerResult:
        resolved = [item for item in state.grounded_conditions if item.status == "resolved"]
        metrics = self._unique([
            item.target for item in resolved if item.semantic_type == "metric" and item.target
        ])
        dimensions = self._unique([
            item.target for item in resolved
            if item.semantic_type == "dimension" and item.target and item.scope is None
        ])
        ambiguities = self._condition_ambiguities(state)

        time_condition = next((item for item in resolved if item.semantic_type == "time"), None)
        time_range = time_condition.value if time_condition else None

        filters: list[dict[str, Any]] = []
        metric_filters: list[dict[str, Any]] = []
        patch_operations: list[dict[str, Any]] = []
        for item in resolved:
            if item.semantic_type == "metric" and item.target and item.operator:
                metric_filter = {
                    "id": "pending", "type": "metric", "target": item.target,
                    "operator": item.operator, "value": item.value,
                    "source": "explicit", "confidence": item.confidence,
                }
                metric_filters.append(metric_filter)
                filters.append(metric_filter)
            elif item.semantic_type == "dimension" and item.target and item.operator and item.scope is None:
                dimension_filter = {
                    "id": "pending", "type": "dimension", "target": item.target,
                    "operator": item.operator,
                    "value": self._canonical_dimension_value(item.target, item.value),
                    "source": "explicit", "confidence": item.confidence,
                }
                filters.append(dimension_filter)
            elif (
                item.semantic_type == "entity" and item.target
                and item.operator in {"exists", "not_exists"} and item.value is None
            ):
                filters.append({
                    "id": "pending", "type": "entity", "target": item.target,
                    "operator": item.operator, "source": "derived_rule",
                    "confidence": item.confidence,
                })
            elif item.semantic_type == "concept" and item.target:
                definition = self.dictionary.get(item.target, {})
                dimension = definition.get("dimension")
                mapped_values = definition.get("value_mapping") or definition.get("values")
                product_concept_lookup = (
                    dimension in {"product_primary_category", "product_secondary_category"}
                    and "客户" not in state.user_query
                )
                customer_segment_analysis = (
                    dimension in {"customer_level", "customer_status", "customer_type", "gender", "age_group", "education", "profession"}
                    and any(marker in state.user_query for marker in ("分布", "客群分析", "群体分析"))
                )
                if product_concept_lookup or customer_segment_analysis:
                    if product_concept_lookup:
                        dimensions = self._unique([*dimensions, dimension])
                    concept_filter = {
                        "id": "pending", "type": "concept", "target": item.target,
                        "operator": item.operator or "eq", "value": item.value if item.value is not None else True,
                        "source": "dictionary", "confidence": item.confidence,
                    }
                elif dimension and mapped_values:
                    dimensions = self._unique([*dimensions, dimension])
                    concept_filter = {
                        "id": "pending", "type": "dimension", "target": dimension,
                        "operator": item.operator or "eq", "value": self._canonical_dimension_value(dimension, mapped_values[0]),
                        "source": "dictionary", "confidence": item.confidence,
                    }
                else:
                    concept_filter = {
                        "id": "pending", "type": "concept", "target": item.target,
                        "operator": item.operator or "eq", "value": item.value if item.value is not None else True,
                        "source": "dictionary", "confidence": item.confidence,
                    }
                filters.append(concept_filter)
            patch_target = item.target
            if item.semantic_type == "concept" and item.target:
                patch_target = self.dictionary.get(item.target, {}).get("dimension") or item.target
            patch_action = item.patch_action
            if (
                patch_action is None
                and item.semantic_type in {"dimension", "concept"}
                and patch_target
                and any(marker in state.user_query for marker in self.context_manager.REMOVE_MARKERS)
            ):
                patch_action = "REMOVE_FILTER"
            if patch_action and any(marker in state.user_query for marker in self.context_manager.REPLACE_MARKERS):
                if patch_action == "ADD_FILTER":
                    patch_action = "REPLACE_FILTER"
                elif patch_action == "ADD_METRIC":
                    patch_action = "REPLACE_METRIC"
            if patch_action:
                patch_operations.append({
                    "action": patch_action,
                    "semantic_type": item.semantic_type,
                    "target": patch_target,
                    "value": item.value,
                    "requested_surface": item.original_surface,
                    "resolution_status": item.status,
                })

        entities = []
        for entity in state.resolved_entities:
            candidates = entity.get("candidates", [])
            if entity.get("status") == "resolved" and candidates:
                candidate = candidates[0]
                entities.append({
                    "entity_type": entity["entity_type"], "surface": entity["surface"],
                    "resolution_status": "resolved",
                    "resolved": {
                        "id": candidate["id"], "name": candidate["name"],
                        "entity_type": entity["entity_type"], "attributes": candidate.get("attributes", {}),
                    },
                    "confidence": max(0.85, float(candidate.get("score", 0.98))),
                    "source": "exact_match" if candidate.get("score") == 1.0 else "fuzzy_match",
                })
                if entity.get("entity_type") == "customer":
                    dimensions = self._unique([*dimensions, "customer"])
                    filters.append({
                        "id": "pending", "type": "dimension", "target": "customer",
                        "operator": "eq", "value": candidate["id"],
                        "source": "entity_resolution", "confidence": max(0.85, float(candidate.get("score", 0.98))),
                    })
                if entity.get("relation_target"):
                    filters.append({
                        "id": "pending", "type": "entity", "target": entity["relation_target"],
                        "operator": entity.get("relation_operator", "exists"), "value": candidate["id"],
                        "source": "entity_resolution", "confidence": max(0.85, float(candidate.get("score", 0.98))),
                    })
            else:
                if not any(item.get("type") == "entity" and item.get("term") == entity.get("surface") for item in ambiguities):
                    ambiguities.append({
                        "term": entity.get("surface", "实体"), "type": "entity",
                        "reason": "实体无法唯一解析。" if entity.get("status") == "ambiguous" else "实体未在受控数据中找到。",
                        "question": "请选择具体实体。" if entity.get("status") == "ambiguous" else "请核对实体名称或代码。",
                        "candidates": candidates,
                    })

        for metric_id in metrics:
            required = bool(self.metrics.get(metric_id, {}).get("constraints", {}).get("required_time_range"))
            if required and time_range is None and not any(item.get("type") == "time" for item in ambiguities):
                ambiguities.append({
                    "term": self.metrics[metric_id].get("name", metric_id), "type": "time",
                    "reason": "该指标口径依赖统计期间，缺少时间时不能安全执行。",
                    "question": f"{self.metrics[metric_id].get('name', metric_id)}需要明确统计时间，因为该指标口径依赖统计期间。请提供日期范围、月份或季度。",
                    "candidates": [],
                })
        ambiguous_metric_ids = {
            candidate
            for item in state.grounded_conditions
            if item.status == "ambiguous" and item.semantic_type == "metric"
            for candidate in item.candidates
            if isinstance(candidate, str)
        }
        if time_range is None and any(
            self.metrics.get(metric_id, {}).get("constraints", {}).get("required_time_range")
            for metric_id in ambiguous_metric_ids
        ) and not any(item.get("type") == "time" for item in ambiguities):
            ambiguities.append({
                "term": "统计期间", "type": "time",
                "reason": "候选指标口径要求明确统计期间。", "question": "请指定统计时间范围。",
                "candidates": [],
            })

        group_by = []
        if any(marker in state.user_query for marker in self.language.get("intent_markers", {}).get("group_analysis", [])):
            filtered_dimensions = {
                item["target"] for item in filters if "logic" not in item and item.get("type") == "dimension"
            }
            group_by = [item for item in dimensions if item not in filtered_dimensions]

        limit_match = re.search(
            r"(?:前|top\s*)(\d+)|(?:最高|最低)的?(\d+)(?:名|个|人)",
            state.user_query,
            flags=re.IGNORECASE,
        )
        limit = int(next(group for group in limit_match.groups() if group is not None)) if limit_match else None
        order_by = []
        ranking_requested = bool(limit or any(
            marker in state.user_query for marker in self.language.get("intent_markers", {}).get("ranking", [])
        ))
        if ranking_requested:
            if metrics:
                order_by = [{"field": metrics[0], "direction": "asc" if "最低" in state.user_query else "desc"}]
            elif not any(item.get("type") == "metric" for item in ambiguities):
                ambiguities.append({
                    "term": "排序指标", "type": "metric", "reason": "排名请求没有匹配到已注册指标。",
                    "question": "不支持当前排名指标；请从已注册指标中选择一个用于排序。",
                    "candidates": [
                        {"metric_id": key, "name": value.get("name", key)}
                        for key, value in list(self.metrics.items())[:10]
                    ],
                })

        intent = self._intent(state.user_query, metrics, metric_filters, group_by, order_by, entities, dimensions)
        if intent == "entity_lookup" and any(item.get("relation_target") for item in state.resolved_entities):
            intent = "customer_selection"
        if intent == "trend_analysis" and time_range is not None and not group_by:
            explicit_time_dimensions = [item for item in dimensions if item in {"date", "month", "quarter"}]
            if explicit_time_dimensions:
                group_by = explicit_time_dimensions
            else:
                dimensions = self._unique([*dimensions, "date"])
                group_by = ["date"]
        if intent == "trend_analysis" and group_by and not order_by and any(
            marker in state.user_query for marker in ("趋势", "走势", "变化趋势")
        ):
            order_by = [{"field": group_by[0], "direction": "asc"}]
        if group_by and any(
            item.semantic_type == "concept"
            and self.dictionary.get(item.target or "", {}).get("dimension") in {
                "customer_level", "customer_status", "customer_type", "gender", "age_group", "education", "profession",
            }
            for item in resolved
        ):
            intent = "segment_analysis"

        if not metrics and not filters and not entities and not ambiguities:
            ambiguities.append({
                "term": state.user_query, "type": "other",
                "reason": "未从受控 Metadata 中检索到可执行语义。",
                "question": "未识别到受支持的指标、维度或概念；请从注册表支持项中选择。",
                "candidates": [],
            })

        if any(marker in state.user_query for marker in self.language.get("logic_markers", {}).get("or", [])) and len(filters) > 1:
            filters = [{"logic": "or", "conditions": filters}]

        subject_mapping = self.language.get("subject_by_dimension", {})
        subject = "customer"
        if intent in {"ranking", "group_analysis", "metric_query", "entity_lookup"}:
            subject = next((subject_mapping[item] for item in dimensions if item in subject_mapping), subject)
            subject_markers = self.language.get("subject_markers", {})
            if not any(marker in state.user_query for marker in subject_markers.get("customer", [])):
                subject = next((
                    subject_type
                    for subject_type in ("product", "branch")
                    if any(marker in state.user_query for marker in subject_markers.get(subject_type, []))
                ), subject)
            if intent == "entity_lookup" and entities:
                entity_subject = {"product": "product", "product_category": "product", "branch": "branch", "parent_branch": "branch"}
                subject = entity_subject.get(entities[0].get("entity_type"), subject)

        status = "needs_clarification" if ambiguities else "ready"
        confidence = 0.5 if ambiguities else 1.0
        having = metric_filters if group_by else []
        if group_by:
            metric_filter_ids = {id(item) for item in metric_filters}
            filters = [item for item in filters if id(item) not in metric_filter_ids]
        plan_data = {
            "version": "1.0", "status": status, "intent": intent, "subject": subject,
            "metrics": metrics, "dimensions": dimensions, "filters": filters, "entities": entities,
            "time_range": time_range, "group_by": group_by, "having": having, "order_by": order_by,
            "limit": limit,
            "output": {
                "mode": "detail" if intent in {"customer_selection", "entity_lookup", "customer_profile", "ranking"} else "aggregate",
                "format": "table", "include_details": intent in {"customer_selection", "entity_lookup", "customer_profile", "ranking"}, "include_explanation": True,
            },
            "ambiguities": ambiguities, "assumptions": [],
            "confidence": {
                "overall": confidence, "intent": confidence, "metrics": confidence,
                "dimensions": confidence, "entities": confidence if state.resolved_entities else 1.0,
                "time": confidence if any(item.get("type") == "time" for item in ambiguities) else 1.0,
                "filters": confidence,
            },
            "context": {"parent_plan_id": None, "operation": "new"},
        }

        previous = state.conversation_context.get("previous_plan")
        if isinstance(previous, dict) and not self.context_manager.is_new_task(state.user_query):
            plan_data, changes = self.context_manager.apply(
                previous, plan_data, state.conversation_context.get("parent_plan_id"), patch_operations,
                query=state.user_query, metrics=self.metrics,
            )
            state.conversation_context["plan_patch"] = {
                "operation": "modify",
                "parent_plan_id": state.conversation_context.get("parent_plan_id")
                or previous.get("context", {}).get("parent_plan_id")
                or "previous_plan",
                "patch_operation": [item["patch_operation"] for item in changes],
                "patch_target": [item["patch_target"] for item in changes],
                "changes": changes,
                "patch_status": self.context_manager.patch_result_status(changes),
                "status_before": previous.get("status"),
                "status_after": plan_data.get("status"),
                "result_plan": deepcopy(plan_data),
            }
        elif isinstance(previous, dict):
            state.conversation_context["plan_patch"] = {
                "operation": "reset",
                "parent_plan_id": state.conversation_context.get("parent_plan_id") or "previous_plan",
                "patch_operation": [], "patch_target": [], "changes": [],
                "status_before": previous.get("status"), "status_after": plan_data.get("status"),
                "result_plan": deepcopy(plan_data),
            }

        self._assign_filter_ids(plan_data["filters"])
        try:
            plan = QueryPlan.model_validate(plan_data)
        except ValidationError as exc:
            return PlannerResult(
                success=False, mode="deterministic", grounded_ids=self._grounded_ids(state),
                error_code="PLANNER_STRUCTURE_ERROR", error_message=str(exc), raw_output=plan_data,
            )
        return PlannerResult(success=True, plan=plan, mode="deterministic", grounded_ids=self._grounded_ids(state))

    def plan(self, state: AgentState) -> PlannerResult:
        return self._provider_plan(state) if self.provider is not None else self._build_deterministic(state)
