from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore

from .matching import normalize_text


class EntityTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.rules = self.store.yaml("entity_rules.yaml").get("entities", {})

    def _resolved_record(self, entity_type: str, row: dict[str, str], score: float) -> dict[str, Any]:
        rule = self.rules[entity_type]
        id_fields = [field for field in rule.get("return_fields", []) if field.endswith("_id")]
        name_fields = [field for field in rule.get("return_fields", []) if field.endswith("_name")]
        identifier = next((row.get(field) for field in id_fields if row.get(field)), None)
        if identifier is None:
            identifier = next((row.get(field) for field in name_fields if row.get(field)), None)
        name = next((row.get(field) for field in name_fields if row.get(field)), identifier)
        return {
            "id": identifier,
            "name": name or str(identifier),
            "entity_type": entity_type,
            "score": round(score, 4),
            "attributes": {field: row.get(field) for field in rule.get("return_fields", [])},
        }

    def search(self, entity_type: str, surface: str, max_candidates: int | None = None) -> ToolResult:
        rule = self.rules.get(entity_type)
        if rule is None:
            return ToolResult.fail("UNKNOWN_ENTITY_TYPE", f"未注册实体类型: {entity_type}", self.store.source("entity_rules.yaml"))

        rows = self.store.csv_rows(rule.get("source_table"))
        search_fields = rule.get("search_fields", [])
        normalized_surface = normalize_text(surface)
        exact_rows = []
        for row in rows:
            if any(normalize_text(row.get(field)) == normalized_surface for field in search_fields):
                exact_rows.append(row)

        limit = max_candidates or int(rule.get("matching", {}).get("max_candidates", 10))
        if exact_rows:
            candidates = [self._resolved_record(entity_type, row, 1.0) for row in exact_rows[:limit]]
            unique = {str(item["id"]): item for item in candidates if item["id"] is not None}
            status = "resolved" if len(unique) == 1 else "ambiguous"
            return ToolResult.ok(
                {"surface": surface, "entity_type": entity_type, "status": status, "candidates": list(unique.values())},
                str(self.store.csv_path_for_table(rule.get("source_table"))),
                0.98 if status == "resolved" else 0.75,
            )

        if not rule.get("matching", {}).get("fuzzy_match") or len(normalized_surface) < 2:
            return ToolResult.ok(
                {"surface": surface, "entity_type": entity_type, "status": "not_found", "candidates": []},
                str(self.store.csv_path_for_table(rule.get("source_table"))),
                0.0,
            )

        scored: list[tuple[float, dict[str, str]]] = []
        for row in rows:
            score = max(
                (SequenceMatcher(None, normalized_surface, normalize_text(row.get(field))).ratio() for field in search_fields),
                default=0.0,
            )
            if score >= 0.72:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        candidates = [self._resolved_record(entity_type, row, score) for score, row in scored[:limit]]
        if not candidates:
            status = "not_found"
            confidence = 0.0
        elif candidates[0]["score"] >= 0.9 and (len(candidates) == 1 or candidates[0]["score"] - candidates[1]["score"] >= 0.08):
            status = "resolved"
            confidence = min(0.9, candidates[0]["score"])
        else:
            status = "ambiguous"
            confidence = min(0.85, candidates[0]["score"])
        return ToolResult.ok(
            {"surface": surface, "entity_type": entity_type, "status": status, "candidates": candidates},
            str(self.store.csv_path_for_table(rule.get("source_table"))),
            confidence,
        )

    def exact_mentions(self, query: str) -> ToolResult:
        normalized_query = normalize_text(query)
        mentions: list[dict[str, str]] = []
        for entity_type, rule in self.rules.items():
            table = rule.get("source_table")
            for row in self.store.csv_rows(table):
                for field in rule.get("search_fields", []):
                    value = row.get(field, "")
                    normalized_value = normalize_text(value)
                    if len(normalized_value) >= 2 and normalized_value in normalized_query:
                        mentions.append({"entity_type": entity_type, "surface": value})
        unique = {(item["entity_type"], item["surface"]): item for item in mentions}
        ordered = sorted(unique.values(), key=lambda item: len(normalize_text(item["surface"])), reverse=True)
        return ToolResult.ok(ordered, self.store.source("entity_rules.yaml"), 1.0 if ordered else 0.0)
