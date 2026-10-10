from __future__ import annotations

from .catalog import MetadataCatalog
from .models import GuardIssue, GuardResult, SQLArtifact
from .parser.sql_ast import SQLAst
from .policy import load_policy


class SchemaGuard:
    def __init__(self, catalog: MetadataCatalog | None = None) -> None:
        self.catalog = catalog or MetadataCatalog()
        self.policy = load_policy("schema_policy.yaml")

    def check(self, ast: SQLAst, artifact: SQLArtifact | None = None) -> GuardResult:
        issues: list[GuardIssue] = []
        ctes = set(ast.ctes)
        aliases = {item.alias: item.name for item in ast.tables}
        real_tables = {item.name for item in ast.tables if item.name not in ctes}
        for table in sorted(real_tables):
            if self.policy.get("require_registered_tables") and table not in self.catalog.tables:
                issues.append(GuardIssue("UNKNOWN_TABLE", f"表 {table} 未在 metadata/tables.yaml 注册。", evidence=table))
        for column in ast.columns:
            table = aliases.get(column.table_alias or "")
            if table and table not in ctes and table in self.catalog.tables:
                if self.policy.get("require_registered_columns") and column.name not in self.catalog.table_columns(table):
                    issues.append(GuardIssue("UNKNOWN_COLUMN", f"字段 {table}.{column.name} 未注册。", evidence={"table": table, "column": column.name}))
        registered_columns = set().union(*(self.catalog.table_columns(table) for table in self.catalog.tables))
        allowed_aliases = set(artifact.selected_columns if artifact else []) | set(ast.ctes)
        unknown_unqualified = sorted(set(ast.unqualified_identifiers) - registered_columns - allowed_aliases)
        if self.policy.get("require_registered_columns") and unknown_unqualified:
            issues.append(GuardIssue("UNKNOWN_COLUMN", "SQL 包含未注册的非限定字段。", evidence=unknown_unqualified))

        provenance = (artifact.logical_plan if artifact else {}).get("joins", [])
        provenance_pairs = {
            (item.get("left"), item.get("right"), item.get("key")) for item in provenance
            if item.get("preaggregated")
        }
        previous_real: str | None = None
        joins_by_right_alias = {item.right_alias: item for item in ast.joins}
        for table_ref in ast.tables:
            if table_ref.source == "from" and table_ref.name not in ctes:
                previous_real = table_ref.name
                continue
            if table_ref.source != "join":
                continue
            right = table_ref.name
            if right in ctes:
                continue
            parsed = joins_by_right_alias.get(table_ref.alias)
            left_table = aliases.get(parsed.left_alias) if parsed and parsed.left_alias else previous_real
            if self.policy.get("require_verified_joins") and left_table and self.catalog.verified_join(left_table, right) is None:
                issues.append(GuardIssue("UNVERIFIED_JOIN", f"{left_table} → {right} 不在 verified join registry。", evidence=[left_table, right]))
            registry_join = self.catalog.verified_join(left_table, right) if left_table else None
            if parsed and registry_join and parsed.left_alias:
                condition = registry_join.get("condition", {})
                expected = {
                    (registry_join.get("left_table"), condition.get("left_column")),
                    (registry_join.get("right_table"), condition.get("right_column")),
                }
                actual = {(left_table, parsed.left_column), (right, parsed.right_column)}
                if self.policy.get("require_verified_joins") and expected != actual:
                    issues.append(GuardIssue("INVALID_JOIN_CONDITION", "Join 字段与 verified registry 不一致。", evidence={"expected": sorted(expected), "actual": sorted(actual)}))
            previous_real = right

        facts = self.catalog.fact_tables()
        for item in provenance:
            left, right = item.get("left"), item.get("right")
            if not self.policy.get("allow_direct_fact_to_fact_join") and left in facts and right in facts and not item.get("preaggregated"):
                issues.append(GuardIssue("DIRECT_FACT_JOIN", "事实表必须先按统一粒度预聚合，禁止直接连接。", evidence=item))
            if item.get("preaggregated") and (left, right, item.get("key")) not in provenance_pairs:
                issues.append(GuardIssue("INVALID_JOIN_PROVENANCE", "预聚合连接缺少可验证的来源。", evidence=item))

        if artifact:
            unknown_metrics = sorted(set(artifact.metric_aliases) - set(self.catalog.metrics))
            if unknown_metrics:
                issues.append(GuardIssue("UNKNOWN_METRIC_PROVENANCE", "SQL 输出包含未注册指标。", evidence=unknown_metrics))
            unknown_sources = sorted(set(artifact.source_tables) - set(self.catalog.tables))
            if unknown_sources:
                issues.append(GuardIssue("UNKNOWN_SOURCE_PROVENANCE", "逻辑计划包含未注册来源表。", evidence=unknown_sources))
            for metric_id, contract in artifact.logical_plan.get("metric_contracts", {}).items():
                registered = self.catalog.metrics.get(metric_id, {})
                expected = {
                    "source_tables": registered.get("source_tables", []) or [],
                    "source_fields": registered.get("source_fields", []) or [],
                    "aggregation": registered.get("aggregation", {}) or {},
                }
                if contract != expected:
                    issues.append(GuardIssue("METRIC_CONTRACT_MISMATCH", f"指标 {metric_id} 的来源或聚合规则与 registry 不一致。", evidence={"expected": expected, "actual": contract}))
        return GuardResult("schema", not any(item.severity == "block" for item in issues), issues, {"tables": sorted(real_tables)})
