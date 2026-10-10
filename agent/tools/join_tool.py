from __future__ import annotations

from collections import deque

from agent.models import ToolResult
from agent.services.metadata_store import MetadataStore


class JoinTool:
    def __init__(self, store: MetadataStore | None = None):
        self.store = store or MetadataStore()
        self.joins = self.store.yaml("joins.yaml")
        self.tables = self.store.yaml("tables.yaml").get("tables", {})

    def get_path(self, source_table: str, target_table: str) -> ToolResult:
        if source_table == target_table:
            return ToolResult.ok({"tables": [source_table], "joins": []}, self.store.source("joins.yaml"))

        graph: dict[str, list[tuple[str, str, dict]]] = {}
        for join_id, definition in self.joins.get("joins", {}).items():
            if not definition.get("verified"):
                continue
            left = definition.get("left_table")
            right = definition.get("right_table")
            graph.setdefault(left, []).append((right, join_id, definition))
            graph.setdefault(right, []).append((left, join_id, definition))

        queue = deque([(source_table, [source_table], [])])
        visited = {source_table}
        while queue:
            current, tables, joins = queue.popleft()
            for neighbor, join_id, definition in graph.get(current, []):
                if neighbor in visited:
                    continue
                next_tables = tables + [neighbor]
                next_joins = joins + [{"join_id": join_id, **definition}]
                if neighbor == target_table:
                    fact_tables = {
                        table_id for table_id, table in self.tables.items()
                        if table.get("table_type") == "fact"
                    }
                    if len(fact_tables.intersection(next_tables)) > 1:
                        return ToolResult.fail(
                            "UNSAFE_JOIN_PATH",
                            "路径跨越多个事实表，必须先分别聚合，不能直接连接。",
                            self.store.source("joins.yaml"),
                            {"tables": next_tables, "joins": next_joins},
                        )
                    return ToolResult.ok(
                        {"tables": next_tables, "joins": next_joins},
                        self.store.source("joins.yaml"),
                    )
                visited.add(neighbor)
                queue.append((neighbor, next_tables, next_joins))

        return ToolResult.fail(
            "JOIN_PATH_NOT_FOUND",
            f"未找到已验证 Join 路径: {source_table} -> {target_table}",
            self.store.source("joins.yaml"),
        )
