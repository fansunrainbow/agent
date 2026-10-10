from __future__ import annotations

from typing import Any

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore

from .matching import best_label_match, normalize_text


class DictionaryTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.dictionary = self.store.yaml("business_dictionary.yaml").get("dictionary", {})
        self.aliases = self.store.yaml("concept_aliases.yaml").get("aliases", {})
        ambiguity = self.store.yaml("ambiguity_rules.yaml")
        self.ambiguity_rules = ambiguity.get("ambiguity_rules", {})
        self.ambiguous_aliases = ambiguity.get("ambiguous_aliases", {})

    def get(self, concept_id: str) -> ToolResult:
        definition = self.dictionary.get(concept_id)
        if definition is None:
            return ToolResult.fail("UNKNOWN_CONCEPT", f"未注册业务概念: {concept_id}", self.store.source("business_dictionary.yaml"))
        return ToolResult.ok({"concept_id": concept_id, **definition}, self.store.source("business_dictionary.yaml"))

    def search(self, query: str, top_k: int = 8, fuzzy_threshold: float = 0.78) -> ToolResult:
        candidates: list[dict[str, Any]] = []
        for concept_id, definition in self.dictionary.items():
            labels = [concept_id, definition.get("name", "")]
            labels.extend(definition.get("aliases", []) or [])
            labels.extend(self.aliases.get(concept_id, []) or [])
            score, matched_alias, match_type = best_label_match(query, [str(item) for item in labels if item])
            if score < fuzzy_threshold:
                continue
            candidates.append({
                "concept_id": concept_id,
                "name": definition.get("name"),
                "matched_alias": matched_alias,
                "match_type": match_type,
                "score": round(score, 4),
                "category": definition.get("category"),
                "dimension": definition.get("dimension"),
                "source": self.store.source("business_dictionary.yaml"),
            })
        candidates.sort(key=lambda item: (item["score"], len(item.get("matched_alias") or "")), reverse=True)
        return ToolResult.ok(candidates[:top_k], self.store.source("business_dictionary.yaml"), 1.0 if candidates else 0.0)

    def find_ambiguities(self, query: str) -> ToolResult:
        normalized_query = normalize_text(query)
        matches: list[dict[str, Any]] = []
        for ambiguity_id, rule in self.ambiguity_rules.items():
            for alias in rule.get("aliases", []) or []:
                if normalize_text(alias) in normalized_query:
                    matches.append({
                        "ambiguity_id": ambiguity_id,
                        "term": alias,
                        "type": "time" if ambiguity_id == "recent" else "business_rule",
                        "options": rule.get("options", []),
                        "question": str(rule.get("clarification_text", "")).strip(),
                        "source": self.store.source("ambiguity_rules.yaml"),
                    })
                    break
        return ToolResult.ok(matches, self.store.source("ambiguity_rules.yaml"), 1.0 if matches else 0.0)

