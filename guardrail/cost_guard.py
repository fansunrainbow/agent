from __future__ import annotations

from .catalog import MetadataCatalog
from .models import GuardIssue, GuardResult, SQLArtifact
from .parser.sql_ast import SQLAst
from .policy import load_policy


class CostGuard:
    def __init__(self, catalog: MetadataCatalog | None = None) -> None:
        self.catalog = catalog or MetadataCatalog()
        self.policy = load_policy("cost_policy.yaml")

    def check(self, ast: SQLAst, artifact: SQLArtifact | None = None) -> GuardResult:
        issues: list[GuardIssue] = []
        real_tables = {item.name for item in ast.tables if item.name not in set(ast.ctes)}
        estimated = sum(self.catalog.row_count(table) for table in real_tables)
        if len(ast.joins) > int(self.policy["max_joins"]):
            issues.append(GuardIssue("TOO_MANY_JOINS", "连接数量超过成本策略上限。", evidence=len(ast.joins)))
        if estimated > int(self.policy["max_estimated_scan_rows"]):
            issues.append(GuardIssue("SCAN_ESTIMATE_EXCEEDED", "预计扫描行数超过成本策略上限。", evidence=estimated))
        if ast.limit is not None and ast.limit > int(self.policy["max_result_rows"]):
            issues.append(GuardIssue("LIMIT_EXCEEDED", "结果行数上限超过策略允许值。", evidence=ast.limit))
        if self.policy.get("require_time_filter_for_fact_tables"):
            if artifact:
                time_filtered = set(artifact.logical_plan.get("time_filtered_tables", []))
            else:
                time_filtered = {
                    table for table in real_tables
                    if table in self.catalog.tables
                    if any(column.table_alias == ref.alias and column.name == self.catalog.tables[table].get("time", {}).get("field")
                           for ref in ast.tables if ref.name == table for column in ast.columns)
                }
            missing = sorted((real_tables & self.catalog.fact_tables()) - time_filtered)
            if missing:
                issues.append(GuardIssue("FACT_TIME_FILTER_REQUIRED", "事实表查询必须包含明确的时间范围。", evidence=missing))
        return GuardResult("cost", not any(item.severity == "block" for item in issues), issues, {"estimated_scan_rows": estimated})
