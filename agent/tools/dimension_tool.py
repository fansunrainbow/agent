from __future__ import annotations

from typing import Any

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore

from .matching import best_label_match, normalize_text


class DimensionTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.dimensions = self.store.yaml("dimensions.yaml").get("dimensions", {})
        self.value_mappings = self.store.yaml("value_mappings.yaml").get("mappings", {})
        self.dynamic_values = self.store.yaml("agent_language.yaml").get("dynamic_dimension_values", {})

    def get(self, dimension_id: str) -> ToolResult:
        definition = self.dimensions.get(dimension_id)
        if definition is None:
            return ToolResult.fail("UNKNOWN_DIMENSION", f"未注册维度: {dimension_id}", self.store.source("dimensions.yaml"))
        return ToolResult.ok({"dimension_id": dimension_id, **definition}, self.store.source("dimensions.yaml"))

    def search(self, query: str, top_k: int = 8, fuzzy_threshold: float = 0.76) -> ToolResult:
        candidates: list[dict[str, Any]] = []
        for dimension_id, definition in self.dimensions.items():
            labels = [dimension_id, definition.get("name", ""), *(definition.get("aliases", []) or [])]
            score, matched_alias, match_type = best_label_match(query, [str(item) for item in labels if item])
            if score < fuzzy_threshold:
                continue
            candidates.append({
                "dimension_id": dimension_id,
                "name": definition.get("name"),
                "matched_alias": matched_alias,
                "match_type": match_type,
                "score": round(score, 4),
                "type": definition.get("type"),
                "source_table": definition.get("source_table"),
                "source_field": definition.get("source_field"),
                "source": self.store.source("dimensions.yaml"),
            })
        candidates.sort(key=lambda item: (item["score"], len(item.get("matched_alias") or "")), reverse=True)
        return ToolResult.ok(candidates[:top_k], self.store.source("dimensions.yaml"), 1.0 if candidates else 0.0)

    def find_values(self, query: str) -> ToolResult:
        normalized_query = normalize_text(query)
        matches: list[dict[str, Any]] = []

        for dimension_id, mapping in self.value_mappings.items():
            semantic_by_code = {
                str(code): str(semantic)
                for semantic, code in (mapping.get("semantic_values", {}) or {}).items()
            }
            aliases = mapping.get("input_aliases", {}) or {}
            for code, label in (mapping.get("values", {}) or {}).items():
                label_text = str(label)
                canonical = semantic_by_code.get(str(code), str(code))
                surfaces = [label_text, *(aliases.get(canonical, []) or [])]
                matched = next((str(item) for item in surfaces if normalize_text(str(item)) and normalize_text(str(item)) in normalized_query), None)
                if matched:
                    matches.append({
                        "dimension_id": dimension_id,
                        "value": canonical,
                        "code": str(code),
                        "matched_surface": matched,
                        "source": self.store.source("value_mappings.yaml"),
                    })

        for dimension_id, lookup_config in self.dynamic_values.items():
            definition = self.dimensions.get(dimension_id, {})
            table = definition.get("source_table")
            field = definition.get("source_field")
            if not table or not field:
                continue
            unique_values = {row.get(field, "") for row in self.store.csv_rows(table)}
            for raw_value in unique_values:
                if not raw_value:
                    continue
                canonical = raw_value
                for suffix in lookup_config.get("strip_suffixes", []):
                    if canonical.endswith(suffix) and len(canonical) > len(suffix):
                        canonical = canonical[:-len(suffix)]
                        break
                if normalize_text(raw_value) in normalized_query or normalize_text(canonical) in normalized_query:
                    matches.append({
                        "dimension_id": dimension_id,
                        "value": canonical,
                        "raw_value": raw_value,
                        "matched_surface": canonical,
                        "source": str(self.store.csv_path_for_table(table)),
                    })

        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for item in matches:
            unique[(item["dimension_id"], str(item["value"]))] = item
        return ToolResult.ok(list(unique.values()), self.store.source("dimensions.yaml"), 1.0 if unique else 0.0)
