from __future__ import annotations

from typing import Any

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore

from .matching import best_label_match


class MetricTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.metrics = self.store.yaml("metrics.yaml").get("metrics", {})
        self.aliases = self.store.yaml("metric_aliases.yaml").get("aliases", {})
        self.constraints = self.store.yaml("metric_constraints.yaml").get("constraints", {})

    def get(self, metric_id: str) -> ToolResult:
        definition = self.metrics.get(metric_id)
        if definition is None:
            return ToolResult.fail("UNKNOWN_METRIC", f"未注册指标: {metric_id}", self.store.source("metrics.yaml"))
        data = {"metric_id": metric_id, **definition}
        data["constraints"] = {
            **self.constraints.get(metric_id, {}),
            **definition.get("constraints", {}),
        }
        return ToolResult.ok(data, self.store.source("metrics.yaml"))

    def search(self, query: str, top_k: int = 8, fuzzy_threshold: float = 0.74) -> ToolResult:
        candidates: list[dict[str, Any]] = []
        for metric_id, definition in self.metrics.items():
            labels = [metric_id, definition.get("name", "")]
            labels.extend(definition.get("aliases", []) or [])
            labels.extend(self.aliases.get(metric_id, []) or [])
            score, matched_alias, match_type = best_label_match(query, [str(item) for item in labels if item])
            if score < fuzzy_threshold:
                continue
            candidates.append({
                "metric_id": metric_id,
                "name": definition.get("name"),
                "matched_alias": matched_alias,
                "match_type": match_type,
                "score": round(score, 4),
                "constraints": {
                    **self.constraints.get(metric_id, {}),
                    **definition.get("constraints", {}),
                },
                "time_semantics": definition.get("time_semantics"),
                "grain": definition.get("grain", []),
                "source_tables": definition.get("source_tables", []),
                "source": self.store.source("metrics.yaml"),
            })
        candidates.sort(key=lambda item: (item["score"], len(item.get("matched_alias") or "")), reverse=True)
        return ToolResult.ok(candidates[:top_k], self.store.source("metrics.yaml"), 1.0 if candidates else 0.0)

