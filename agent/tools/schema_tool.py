from __future__ import annotations

from typing import Any

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore

from .matching import best_label_match


class SchemaTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.tables = self.store.yaml("tables.yaml").get("tables", {})

    def get_table(self, table_id: str) -> ToolResult:
        table = self.tables.get(table_id)
        if table is None:
            return ToolResult.fail("UNKNOWN_TABLE", f"未注册表: {table_id}", self.store.source("tables.yaml"))
        return ToolResult.ok({"table_id": table_id, **table}, self.store.source("tables.yaml"))

    def search(self, query: str, top_k: int = 8) -> ToolResult:
        candidates: list[dict[str, Any]] = []
        for table_id, table in self.tables.items():
            labels = [table_id, table.get("display_name", ""), table.get("description", "")]
            score, matched_alias, match_type = best_label_match(query, [str(item) for item in labels if item])
            column_matches = []
            for column_id, column in (table.get("columns", {}) or {}).items():
                column_score, column_alias, column_match_type = best_label_match(
                    query,
                    [column_id, column.get("description", ""), column.get("role", "")],
                )
                if column_score >= 0.85:
                    column_matches.append({
                        "column_id": column_id,
                        "matched_alias": column_alias,
                        "match_type": column_match_type,
                        "score": round(column_score, 4),
                    })
            if score >= 0.78 or column_matches:
                candidates.append({
                    "table_id": table_id,
                    "display_name": table.get("display_name"),
                    "grain": table.get("grain"),
                    "time": table.get("time"),
                    "matched_alias": matched_alias,
                    "score": round(max(score, max((c["score"] for c in column_matches), default=0)), 4),
                    "columns": column_matches,
                    "source": self.store.source("tables.yaml"),
                })
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return ToolResult.ok(candidates[:top_k], self.store.source("tables.yaml"), 1.0 if candidates else 0.0)

