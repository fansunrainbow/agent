from __future__ import annotations

import re
from typing import Any

from agent.models import AgentState, GroundedCondition
from agent.services.metadata_store import MetadataStore
from agent.tools import EntityTool


class EntityResolver:
    """Resolve high-cardinality entities only through configured datasets."""

    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.entity_tool = EntityTool(self.store)
        self.language = self.store.yaml("agent_language.yaml")
        self.dimensions = self.store.yaml("dimensions.yaml").get("dimensions", {})
        self.entity_rules = self.store.yaml("entity_rules.yaml").get("entities", {})

    def extract_mentions(self, query: str, state: AgentState | None = None) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        typed_conditions = [
            item for item in (state.grounded_conditions if state is not None else [])
            if item.status == "resolved" and item.semantic_type in {"metric", "dimension", "concept"}
        ]

        def covered_by_categorical_dimension(entity_type: str, surface: str) -> bool:
            entity_table = self.entity_rules.get(entity_type, {}).get("source_table")
            return any(
                self.dimensions.get(item.target or "", {}).get("type") == "categorical"
                and self.dimensions.get(item.target or "", {}).get("source_table") == entity_table
                and item.original_surface
                and (item.original_surface in surface or surface in item.original_surface)
                for item in typed_conditions
                if item.semantic_type == "dimension"
            )
        for entity_type, config in self.language.get("entity_mentions", {}).items():
            for pattern in config.get("patterns", []):
                for match in re.finditer(pattern, query, flags=re.IGNORECASE):
                    surface = match.groupdict().get("surface")
                    if not surface:
                        continue
                    surface = surface.strip(" 的")
                    if covered_by_categorical_dimension(entity_type, surface):
                        continue
                    if any(
                        item.semantic_type == "metric" and surface and surface in item.original_surface
                        for item in typed_conditions
                    ):
                        continue
                    is_identifier = bool(re.fullmatch(r"[A-Za-z]?\d{4,}", surface))
                    if not is_identifier and (
                        re.search(r"\d|超过|低于|高于|大于|小于|占比|金额|交易额|次数|资产", surface)
                    ):
                        continue
                    relation_target = None
                    for marker, target in config.get("relation_targets", {}).items():
                        if marker in match.group(0):
                            relation_target = target
                            break
                    mentions.append({
                        "entity_type": entity_type,
                        "surface": surface,
                        "relation_target": relation_target,
                        "relation_operator": "not_exists" if relation_target and re.search(
                            r"(?:没有|未|不|无)(?:持有|持仓|交易|买入|卖出)",
                            query[max(0, match.start() - 10):match.end() + 2],
                        ) else "exists",
                    })

        exact = self.entity_tool.exact_mentions(query)
        customer_identifiers = re.findall(r"C\d{15,18}", query, flags=re.IGNORECASE)
        for item in exact.data or []:
            entity_type = item["entity_type"]
            surface = str(item["surface"])
            if entity_type == "product" and any(surface in identifier for identifier in customer_identifiers):
                continue
            if covered_by_categorical_dimension(entity_type, surface):
                continue
            if any(
                condition.semantic_type == "metric" and surface in condition.original_surface
                for condition in typed_conditions
            ):
                continue
            if entity_type == "product_category" and not (
                "类别" in query or "分类" in query or query.strip(" 查询。？?") == surface
            ):
                continue
            if entity_type == "customer" and not (
                re.fullmatch(r"[A-Za-z]?\d{4,}", surface) or "客户画像" in query or "指定客户" in query
            ):
                continue
            relation_target = None
            position = query.find(surface)
            prefix = query[max(0, position - 6):position] if position >= 0 else ""
            suffix = query[position + len(surface):position + len(surface) + 6] if position >= 0 else ""
            if entity_type == "product":
                if any(marker in prefix or marker in suffix for marker in ("持有", "持仓")):
                    relation_target = "held_product"
                elif any(marker in prefix or marker in suffix for marker in ("交易", "买入", "卖出")):
                    relation_target = "traded_product"
            elif entity_type == "product_category" and ("类别" in query or "分类" in query):
                relation_target = "product_category"
            elif entity_type in {"branch", "parent_branch"} and "客户" in query:
                relation_target = entity_type
            mentions.append({
                "entity_type": entity_type, "surface": surface, "relation_target": relation_target,
                "relation_operator": "not_exists" if relation_target and any(
                    marker in prefix for marker in ("没有持有", "未持有", "不持有", "无持仓", "没有交易", "未交易")
                ) else "exists",
            })
        dimension_hints = {
            item.target: item.original_surface
            for item in typed_conditions
            if item.semantic_type == "dimension" and item.target
        }
        by_surface: dict[str, list[dict[str, Any]]] = {}
        for item in mentions:
            by_surface.setdefault(item["surface"], []).append(item)
        pruned: list[dict[str, Any]] = []
        for surface, candidates in by_surface.items():
            hinted = [
                item for item in candidates
                if item["entity_type"] in dimension_hints
                and dimension_hints[item["entity_type"]] in surface
            ]
            pruned.extend(hinted or candidates)
        mentions = pruned
        unique = {(item["entity_type"], item["surface"]): item for item in mentions}
        ordered = sorted(unique.values(), key=lambda item: len(item["surface"]), reverse=True)
        selected: list[dict[str, Any]] = []
        for item in ordered:
            if any(
                item["entity_type"] == old["entity_type"] and item["surface"] in old["surface"]
                for old in selected
            ):
                continue
            selected.append(item)
        return selected

    def resolve(self, state: AgentState) -> AgentState:
        resolved_entities = []
        product_category_grounded = any(
            item.status == "resolved"
            and item.semantic_type == "dimension"
            and item.target in {"product_primary_category", "product_secondary_category"}
            for item in state.grounded_conditions
        )
        relation_target = None
        if product_category_grounded and "客户" in state.user_query:
            if any(marker in state.user_query for marker in ("持有", "持仓")):
                relation_target = "held_product"
            elif any(marker in state.user_query for marker in ("交易", "买入", "卖出")):
                relation_target = "traded_product"
        if relation_target:
            negative = any(marker in state.user_query for marker in (
                "没有持有", "未持有", "不持有", "无持仓",
                "没有交易", "未交易", "不交易",
            ))
            state.grounded_conditions.append(GroundedCondition(
                condition_id=f"c{len(state.grounded_conditions) + 1}",
                original_surface="产品关系",
                semantic_type="entity",
                target=relation_target,
                operator="not_exists" if negative else "exists",
                value=None,
                source="metadata/entity_relations.yaml",
                confidence=1.0,
                status="resolved",
            ))
        mentions = self.extract_mentions(state.user_query, state)
        for mention in mentions:
            result = self.entity_tool.search(mention["entity_type"], mention["surface"])
            payload = result.data or {
                "surface": mention["surface"],
                "entity_type": mention["entity_type"],
                "status": "not_found",
                "candidates": [],
            }
            payload["relation_target"] = mention.get("relation_target")
            payload["relation_operator"] = mention.get("relation_operator", "exists")
            payload["source"] = result.source
            resolved_entities.append(payload)
            candidates = payload.get("candidates", [])
            condition_status = "resolved" if payload.get("status") == "resolved" else (
                "ambiguous" if payload.get("status") == "ambiguous" else "unsupported"
            )
            state.grounded_conditions.append(GroundedCondition(
                condition_id=f"c{len(state.grounded_conditions) + 1}",
                original_surface=mention["surface"],
                semantic_type="entity",
                target=mention["entity_type"],
                operator=mention.get("relation_operator", "exists") if mention.get("relation_target") else None,
                value=candidates[0].get("id") if condition_status == "resolved" and candidates else None,
                source=result.source,
                confidence=result.confidence,
                status=condition_status,
                candidates=candidates if condition_status != "resolved" else [],
                reason=(
                    "实体存在多个候选，不能自动选择。" if condition_status == "ambiguous"
                    else "实体未在受控数据中找到。" if condition_status == "unsupported" else None
                ),
                question=(
                    "请选择具体实体。" if condition_status == "ambiguous"
                    else "请核对实体名称或代码。" if condition_status == "unsupported" else None
                ),
                patch_action="ADD_FILTER" if mention.get("relation_target") else None,
            ))
            state.grounding_sources.append({
                "type": "entity",
                "id": payload.get("candidates", [{}])[0].get("id") if payload.get("candidates") else None,
                "surface": mention["surface"],
                "source": result.source,
                "confidence": result.confidence,
            })

        state.resolved_entities = resolved_entities
        resolved_surfaces = [
            item.get("surface", "") for item in resolved_entities if item.get("status") == "resolved"
        ]
        if resolved_surfaces:
            state.grounded_conditions = [
                condition for condition in state.grounded_conditions
                if condition.semantic_type in {"time", "metric", "entity", "prediction_request", "suitability_request", "unsupported_attribute"}
                or not any(
                    condition.original_surface and (
                        condition.original_surface in surface
                        or (condition.status == "unsupported" and surface in condition.original_surface)
                        or (condition.semantic_type in {"dimension", "concept"} and condition.original_surface == surface)
                    )
                    for surface in resolved_surfaces
                )
            ]
            for index, condition in enumerate(state.grounded_conditions, 1):
                condition.condition_id = f"c{index}"
        state.add_trace(
            "resolve_entities",
            "success",
            source=self.store.source("entity_rules.yaml"),
            input_summary=[item["surface"] for item in mentions],
            output_summary=[{
                "surface": item.get("surface"),
                "entity_type": item.get("entity_type"),
                "status": item.get("status"),
            } for item in resolved_entities],
        )
        return state
