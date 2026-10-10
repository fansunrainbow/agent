from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from agent.clarification import ClarificationEngine
from agent.llm import StructuredLLMProvider
from agent.models import AgentState, AgentStatus
from agent.planner import Planner
from agent.repair import RepairEngine
from agent.services.audit_logger import JsonlAuditLogger
from agent.services.concept_expander import ConceptExpander
from agent.services.entity_resolver import EntityResolver
from agent.services.metadata_store import MetadataStore
from agent.services.semantic_retriever import SemanticRetriever
from agent.tool_router import ToolRouter
from scripts.validate_query_plan import load_registries, validate_plan_data


class AgentOrchestrator:
    """Stage 5 state machine. It produces validated Query Plans, never SQL."""

    def __init__(
        self,
        provider: StructuredLLMProvider | None = None,
        audit_log: Path | None = None,
        store: MetadataStore | None = None,
    ):
        self.store = store or MetadataStore()
        self.retriever = SemanticRetriever(self.store)
        self.concept_expander = ConceptExpander(self.store)
        self.entity_resolver = EntityResolver(self.store)
        self.router = ToolRouter()
        self.planner = Planner(self.store, provider=provider)
        self.repair = RepairEngine()
        self.clarification = ClarificationEngine()
        self.registries = load_registries()
        self.dictionary = self.store.yaml("business_dictionary.yaml").get("dictionary", {})
        self.logger = JsonlAuditLogger(audit_log) if audit_log else None

    @staticmethod
    def _validation_summary(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "valid": result.get("valid", False),
            "error_codes": [item.get("code") for item in result.get("errors", [])],
            "warning_codes": [item.get("code") for item in result.get("warnings", [])],
        }

    @staticmethod
    def _serialize_plan(plan: Any) -> dict[str, Any]:
        """Keep required nullable root fields while pruning invalid nested nulls."""
        data = plan.model_dump(mode="json")

        def prune_nested(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: prune_nested(item) for key, item in value.items() if item is not None}
            if isinstance(value, list):
                return [prune_nested(item) for item in value]
            return value

        for field in ("time_range", "entities"):
            value = data.get(field)
            if isinstance(value, dict):
                data[field] = prune_nested(value)
            elif isinstance(value, list):
                data[field] = prune_nested(value)
        return data

    def _grounding_errors(self, state: AgentState, plan: dict[str, Any]) -> list[dict[str, Any]]:
        previous = state.conversation_context.get("previous_plan") or {}
        allowed_metrics = {
            item.target for item in state.grounded_conditions
            if item.status == "resolved" and item.semantic_type == "metric" and item.target
        } | set(previous.get("metrics", []))
        allowed_dimensions = {
            item.target for item in state.grounded_conditions
            if item.status == "resolved" and item.semantic_type == "dimension" and item.target
        } | set(previous.get("dimensions", []))
        allowed_dimensions |= {
            item.get("target") for item in previous.get("filters", [])
            if "logic" not in item and item.get("type") == "dimension" and item.get("target")
        }
        allowed_concepts = {
            item.target for item in state.grounded_conditions
            if item.status == "resolved" and item.semantic_type == "concept" and item.target
        }
        for concept_id in allowed_concepts:
            dimension = self.dictionary.get(concept_id, {}).get("dimension")
            if dimension:
                allowed_dimensions.add(dimension)
        allowed_concepts |= {
            item.get("target") for item in previous.get("filters", [])
            if "logic" not in item and item.get("type") == "concept"
        }
        allowed_entity_ids = {
            str(item.value) for item in state.grounded_conditions
            if item.status == "resolved" and item.semantic_type == "entity" and item.value is not None
        } | {
            str(item.get("resolved", {}).get("id")) for item in previous.get("entities", [])
            if item.get("resolved", {}).get("id") is not None
        }
        allowed_entity_relations = {
            item.target for item in state.grounded_conditions
            if item.status == "resolved" and item.semantic_type == "entity"
            and item.target and item.operator in {"exists", "not_exists"}
        }
        if any(
            item.get("entity_type") == "customer" and item.get("status") == "resolved"
            for item in state.resolved_entities
        ):
            # A resolved customer entity is projected and filtered through the
            # registered customer dimension by the deterministic planner.
            allowed_dimensions.add("customer")
        if plan.get("intent") == "trend_analysis" and any(
            item.status == "resolved" and item.semantic_type == "time" for item in state.grounded_conditions
        ):
            allowed_dimensions.add("date")

        errors = []
        for index, metric in enumerate(plan.get("metrics", [])):
            if metric not in allowed_metrics:
                errors.append({
                    "code": "UNGROUNDED_SEMANTIC", "path": f"metrics[{index}]", "value": metric,
                    "message": "Planner 输出了 Grounded Conditions 中不存在的 Metric。",
                })
        for index, dimension in enumerate(plan.get("dimensions", [])):
            if dimension not in allowed_dimensions:
                errors.append({
                    "code": "UNGROUNDED_SEMANTIC", "path": f"dimensions[{index}]", "value": dimension,
                    "message": "Planner 输出了 Grounded Conditions 中不存在的 Dimension。",
                })

        def check_filters(nodes: list[dict[str, Any]], path: str) -> None:
            for index, item in enumerate(nodes):
                item_path = f"{path}[{index}]"
                if "logic" in item:
                    check_filters(item.get("conditions", []), f"{item_path}.conditions")
                elif item.get("type") == "metric" and item.get("target") not in allowed_metrics:
                    errors.append({
                        "code": "UNGROUNDED_SEMANTIC", "path": f"{item_path}.target", "value": item.get("target"),
                        "message": "Planner 输出了未 Ground 的 Metric Filter。",
                    })
                elif item.get("type") == "dimension" and item.get("target") not in allowed_dimensions:
                    errors.append({
                        "code": "UNGROUNDED_SEMANTIC", "path": f"{item_path}.target", "value": item.get("target"),
                        "message": "Planner 输出了未 Ground 的 Dimension Filter。",
                    })
                elif item.get("type") == "concept" and item.get("target") not in allowed_concepts:
                    errors.append({
                        "code": "UNGROUNDED_SEMANTIC", "path": f"{item_path}.target", "value": item.get("target"),
                        "message": "Planner 输出了未 Ground 的 Concept Filter。",
                    })
                elif (
                    item.get("type") == "entity"
                    and item.get("target") not in allowed_entity_relations
                    and str(item.get("value")) not in allowed_entity_ids
                ):
                    errors.append({
                        "code": "UNGROUNDED_SEMANTIC", "path": f"{item_path}.value", "value": item.get("value"),
                        "message": "Planner 输出了未 Ground 的 Entity Filter。",
                    })

        check_filters(plan.get("filters", []), "filters")
        for index, entity in enumerate(plan.get("entities", [])):
            entity_id = entity.get("resolved", {}).get("id")
            if entity_id is not None and str(entity_id) not in allowed_entity_ids:
                errors.append({
                    "code": "UNGROUNDED_SEMANTIC", "path": f"entities[{index}].resolved.id", "value": entity_id,
                    "message": "Planner 输出了 Grounded Conditions 中不存在的 Entity。",
                })
        return errors

    def run(self, user_query: str, conversation_context: dict[str, Any] | None = None) -> AgentState:
        started = perf_counter()
        context = deepcopy(conversation_context) if conversation_context else {}
        previous_time = (context.get("previous_plan") or {}).get("time_range")
        if "reference_date" not in context and isinstance(previous_time, dict):
            reference_period = previous_time.get("period") if isinstance(previous_time.get("period"), dict) else previous_time
            reference_year = reference_period.get("year")
            if isinstance(reference_year, int):
                context["reference_date"] = f"{reference_year:04d}-01-01"
        state = AgentState(user_query=user_query, conversation_context=context)
        try:
            self.retriever.retrieve(state)
            self.concept_expander.expand(state)
            self.entity_resolver.resolve(state)
            state.routed_tools = self.router.route(state)
            state.add_trace("route_tools", "success", output_summary=state.routed_tools)

            planned = self.planner.plan(state)
            state.add_trace(
                "build_query_plan",
                "success" if planned.success else "failed",
                source=planned.mode,
                output_summary={"grounded_ids": planned.grounded_ids, "error_code": planned.error_code},
            )
            if not planned.success or planned.plan is None:
                state.clarification = self.clarification.from_plan_and_validation(
                    planned.raw_output, None, planned.error_message or "无法生成结构化查询计划，请补充请求细节。",
                    state.grounded_conditions,
                )
                state.clarification_needed = state.clarification.needed
                state.status = AgentStatus.NEEDS_CLARIFICATION if state.clarification_needed else AgentStatus.ERROR
                return self._finish(state, started)

            state.query_plan = self._serialize_plan(planned.plan)
            validation = validate_plan_data(state.query_plan, self.registries, source=f"agent:{state.query_id}")
            grounding_errors = self._grounding_errors(state, state.query_plan)
            if grounding_errors:
                validation["errors"].extend(grounding_errors)
                validation["valid"] = False
            state.validation_result = validation
            state.add_trace("validate_query_plan", "success" if validation["valid"] else "failed", output_summary=self._validation_summary(validation))

            while not validation["valid"] and state.repair_count < self.repair.MAX_ATTEMPTS and self.repair.is_repairable(validation):
                repaired, repair_info = self.repair.repair(state.query_plan, validation)
                state.repair_count += 1
                state.repair_history.append(repair_info)
                state.add_trace("repair_query_plan", "changed" if repair_info["changed"] else "unchanged", output_summary=repair_info)
                if not repair_info["changed"]:
                    break
                state.query_plan = repaired
                validation = validate_plan_data(state.query_plan, self.registries, source=f"agent:{state.query_id}:repair{state.repair_count}")
                grounding_errors = self._grounding_errors(state, state.query_plan)
                if grounding_errors:
                    validation["errors"].extend(grounding_errors)
                    validation["valid"] = False
                state.validation_result = validation
                state.add_trace("validate_repaired_plan", "success" if validation["valid"] else "failed", output_summary=self._validation_summary(validation))

            patch_audit = state.conversation_context.get("plan_patch")
            if isinstance(patch_audit, dict):
                if not validation["valid"]:
                    state.query_plan["status"] = "needs_clarification"
                patch_audit["validation_result"] = deepcopy(validation)
                patch_audit["status_after"] = state.query_plan.get("status")
                patch_audit["result_plan"] = deepcopy(state.query_plan)
                patch_audit.setdefault("patch_status", "APPLIED")
                state.add_trace(
                    "apply_plan_patch",
                    "success" if validation["valid"] and patch_audit["patch_status"] == "APPLIED" else "failed",
                    output_summary={
                        "operation": patch_audit.get("operation"),
                        "patch_operation": patch_audit.get("patch_operation", []),
                        "patch_target": patch_audit.get("patch_target", []),
                        "patch_status": patch_audit.get("patch_status"),
                        "changes": [{
                            key: item.get(key) for key in (
                                "patch_operation", "patch_target", "old_value", "requested_new_value",
                                "resolution_status", "patch_status",
                            )
                        } for item in patch_audit.get("changes", [])],
                        "validation": self._validation_summary(validation),
                    },
                )

            if validation["valid"] and state.query_plan.get("status") == "ready":
                state.status = AgentStatus.READY
            elif validation["valid"] and state.query_plan.get("status") == "needs_clarification":
                state.clarification = self.clarification.from_plan_and_validation(
                    state.query_plan, validation, grounded_conditions=state.grounded_conditions,
                )
                state.clarification_needed = state.clarification.needed
                state.status = AgentStatus.UNSUPPORTED if state.clarification.unsupported else AgentStatus.NEEDS_CLARIFICATION
            else:
                state.clarification = self.clarification.from_plan_and_validation(
                    state.query_plan, validation, grounded_conditions=state.grounded_conditions,
                )
                state.clarification_needed = state.clarification.needed
                state.status = AgentStatus.UNSUPPORTED if state.clarification.unsupported else AgentStatus.NEEDS_CLARIFICATION
            return self._finish(state, started)
        except Exception as exc:
            state.status = AgentStatus.ERROR
            state.add_trace("orchestrator", "failed", output_summary={"error_type": type(exc).__name__, "message": str(exc)})
            return self._finish(state, started)

    def _finish(self, state: AgentState, started: float) -> AgentState:
        state.latency_ms = round((perf_counter() - started) * 1000, 3)
        state.add_trace("finish", state.status.value, output_summary={"latency_ms": state.latency_ms})
        if self.logger:
            self.logger.write(state)
        return state


def run_agent(user_query: str, conversation_context: dict[str, Any] | None = None) -> AgentState:
    return AgentOrchestrator().run(user_query, conversation_context)
