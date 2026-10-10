from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import date, timedelta
import re
from typing import Any

from scripts.validate_query_plan import load_registries, validate_plan_data

from .catalog import MetadataCatalog
from .logical_planner import LogicalPlan, LogicalPlanner, LogicalPlanningError
from .models import SQLArtifact
from .policy import load_policy


class SQLGenerationError(ValueError):
    def __init__(self, code: str, message: str, evidence: Any | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence


class ParameterBag:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def add(self, value: Any) -> str:
        name = f"p{len(self.values) + 1}"
        self.values[name] = value
        return f":{name}"


class SQLGenerator:
    """Deterministic Query Plan -> SQL compiler. No LLM and no natural language input."""

    IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
    AGGREGATE = re.compile(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", re.IGNORECASE)

    def __init__(self, catalog: MetadataCatalog | None = None) -> None:
        self.catalog = catalog or MetadataCatalog()
        self.mapping = load_policy("logical_mapping.yaml")
        self.cost_policy = load_policy("cost_policy.yaml")
        self.registries = load_registries()
        self.logical_planner = LogicalPlanner(self.catalog, self.mapping)

    def generate(self, query_id: str, query_plan: dict[str, Any], validation_result: dict[str, Any] | None) -> SQLArtifact:
        plan = deepcopy(query_plan)
        if plan.get("status") != "ready":
            raise SQLGenerationError("PLAN_NOT_READY", "Stage 6 只接受 status=ready 的 Query Plan。")
        if not validation_result or not validation_result.get("valid"):
            raise SQLGenerationError("PLAN_NOT_VALIDATED", "缺少 Stage 5 有效验证结果。")
        independent = validate_plan_data(plan, self.registries, source=f"guardrail:{query_id}")
        if not independent["valid"]:
            raise SQLGenerationError("PLAN_REVALIDATION_FAILED", "Stage 6 独立复验失败。", independent["errors"])
        try:
            logical = self.logical_planner.build(plan)
        except LogicalPlanningError as exc:
            raise SQLGenerationError(exc.code, str(exc), exc.evidence) from exc
        params = ParameterBag()
        sql, selected, time_filtered = self._compile(plan, logical, params)
        logical_dict = logical.to_dict()
        logical_dict["time_filtered_tables"] = sorted(time_filtered)
        logical_dict["parameter_names"] = list(params.values)
        logical_dict["metric_contracts"] = {
            metric_id: {
                "source_tables": self.catalog.metrics[metric_id].get("source_tables", []) or [],
                "source_fields": self.catalog.metrics[metric_id].get("source_fields", []) or [],
                "aggregation": self.catalog.metrics[metric_id].get("aggregation", {}) or {},
            }
            for metric_id in logical.metric_order
        }
        return SQLArtifact(
            query_id=query_id, sql=sql, params=params.values, query_plan=plan,
            logical_plan=logical_dict, metric_aliases=logical.requested_metrics,
            selected_columns=selected, source_tables=logical.source_tables,
        )

    def _compile(self, plan: dict[str, Any], logical: LogicalPlan, params: ParameterBag) -> tuple[str, list[str], set[str]]:
        if logical.subject not in {"customer", "branch", "product"}:
            raise SQLGenerationError(
                "SQL_UNSUPPORTED_COMBINATION",
                f"Subject {logical.subject} 尚无可证明安全的 SQL 粒度转换。",
                logical.subject,
            )
        date_bounds = self._date_bounds(logical.time_range)
        if plan.get("intent") == "trend_analysis" and plan.get("group_by"):
            return self._compile_time_series(plan, logical, date_bounds, params)
        ctes: list[str] = []
        time_filtered: set[str] = set()
        where_nodes = plan.get("filters", [])
        scoped_relations = self._scoped_relation_filters(where_nodes)
        relation_scoped_dimensions = {
            node["target"]
            for _, dimension_nodes in scoped_relations
            for node in dimension_nodes
        }
        metric_scoped_filters = self._metric_scoped_dimension_filters(plan, logical)
        metric_scoped_entities = self._metric_scoped_entity_filters(plan, logical)
        scoped_dimensions = relation_scoped_dimensions | {
            node["target"] for node in metric_scoped_filters
        }
        dimension_bindings, base_joins, base_where, product_bridge = self._dimension_bindings(
            plan, logical, date_bounds, params, excluded_dimensions=scoped_dimensions,
        )
        dimension_fields = {key: value["source_field"] for key, value in dimension_bindings.items()}
        base_entity_dimension_nodes = [
            node for node in where_nodes
            if "logic" not in node and node.get("type") == "entity"
            and node.get("value") is not None
            and (self.catalog.entity_relation(node.get("target")) or {}).get("target_dimension")
            in dimension_bindings
        ]
        base_filter_nodes = [
            node for node in where_nodes
            if "logic" not in node
            and node.get("type") == "dimension"
            and node.get("target") not in scoped_dimensions
            and (node.get("target") == "customer" or node.get("target") in dimension_bindings)
        ]
        for node in base_filter_nodes:
            target = node["target"]
            left = "c.pty_id" if target == "customer" else dimension_bindings[target]["expression"]
            base_where.append(self._operator(
                left, node.get("operator"),
                self.catalog.storage_value(target, node.get("value")), params,
            ))
        for node in base_entity_dimension_nodes:
            relation = self.catalog.entity_relation(node.get("target")) or {}
            target = relation["target_dimension"]
            comparison = "neq" if node.get("operator") == "not_exists" else "eq"
            base_where.append(self._operator(
                dimension_bindings[target]["expression"], comparison, node.get("value"), params,
            ))
        base_select = ["c.pty_id AS pty_id"] + [
            f"{binding['expression']} AS {dimension}"
            for dimension, binding in dimension_bindings.items()
        ]
        base_lines = [
            "base_entities AS (",
            "  SELECT DISTINCT " + ", ".join(base_select),
            "  FROM ads_cust_info_d AS c",
            *("  " + item for item in base_joins),
        ]
        if base_where:
            base_lines.append("  WHERE " + " AND ".join(base_where))
            if product_bridge:
                time_filtered.add(product_bridge)
        base_lines.append(")")
        ctes.append("\n".join(base_lines))

        product_dimensions = {
            key: value for key, value in dimension_bindings.items()
            if value["source_table"] == "dim_product"
        }

        built: set[str] = set()
        for metric_id in logical.metric_order:
            metric = self.catalog.metrics[metric_id]
            dependencies = metric.get("derived_from", []) or []
            if dependencies:
                ctes.append(self._derived_metric_cte(metric_id, metric, dependencies, product_dimensions))
            else:
                metric_dimensions = product_dimensions if self._primary_metric_table(metric) == product_bridge else {}
                if (
                    product_dimensions
                    and metric_id in logical.requested_metrics
                    and not metric_dimensions
                    and not self._aggregates_from_base_key(metric)
                ):
                    raise SQLGenerationError(
                        "SQL_UNSUPPORTED_COMBINATION",
                        f"指标 {metric_id} 与产品维度不共享同一已验证事实粒度。",
                    )
                scoped_for_metric = [
                    node for node in metric_scoped_filters
                    if self.catalog.verified_join(
                        self._primary_metric_table(metric) or "",
                        self.catalog.dimensions.get(node["target"], {}).get("source_table", ""),
                    )
                ]
                scoped_entities_for_metric = [
                    node for node in metric_scoped_entities
                    if (self.catalog.entity_relation(node.get("target")) or {}).get("target_table")
                    == self._primary_metric_table(metric)
                ]
                cte, filtered = self._leaf_metric_cte(
                    metric_id, metric, date_bounds, params, metric_dimensions, scoped_for_metric,
                    scoped_entities_for_metric, bool(base_filter_nodes),
                )
                ctes.append(cte)
                time_filtered.update(filtered)
            built.add(metric_id)

        requested = logical.requested_metrics
        main_joins = []
        for metric in requested:
            conditions = [f"b.pty_id = m_{metric}.pty_id"]
            if product_dimensions and not self._aggregates_from_base_key(self.catalog.metrics[metric]):
                conditions.extend(f"b.{dimension} = m_{metric}.{dimension}" for dimension in product_dimensions)
            main_joins.append(f"LEFT JOIN metric_{metric} AS m_{metric} ON " + " AND ".join(conditions))
        selected: list[str] = []
        select_sql: list[str] = []
        ranking_mode = plan.get("intent") == "ranking"
        aggregate_mode = not ranking_mode and (
            plan.get("output", {}).get("mode") in {"aggregate", "summary"}
            or plan.get("intent") in {"metric_query", "group_analysis", "trend_analysis"}
        )
        group_dims = plan.get("group_by", [])
        if group_dims:
            for dimension in group_dims:
                select_sql.append(f"b.{dimension} AS {dimension}")
                selected.append(dimension)
        elif not aggregate_mode:
            select_sql.append("b.pty_id AS pty_id")
            selected.append("pty_id")
            for dimension in logical.dimensions:
                if dimension != "customer" and dimension not in scoped_dimensions:
                    select_sql.append(f"b.{dimension} AS {dimension}")
                    selected.append(dimension)
        for metric_id in requested:
            expression = self._outer_metric(metric_id, aggregate_mode or bool(group_dims), "b.pty_id")
            select_sql.append(f"{expression} AS {metric_id}")
            selected.append(metric_id)
        if not select_sql:
            select_sql = ["b.pty_id AS pty_id"]
            selected = ["pty_id"]

        consumed = {
            id(node) for relation, dimensions in scoped_relations for node in [relation, *dimensions]
        } | {id(node) for node in metric_scoped_filters} | {
            id(node) for node in metric_scoped_entities
        } | {id(node) for node in base_filter_nodes} | {
            id(node) for node in base_entity_dimension_nodes
        }
        where_parts = [
            self._relation_dimension_predicate(relation, dimensions, params, date_bounds, logical)
            for relation, dimensions in scoped_relations
        ]
        remaining_nodes = [node for node in where_nodes if id(node) not in consumed]
        remaining_sql = self._compile_filter_list(remaining_nodes, dimension_fields, requested, params, date_bounds)
        if remaining_sql:
            where_parts.append(remaining_sql)
        where_sql = " AND ".join(where_parts)
        if date_bounds:
            for node in self._walk_filters(where_nodes):
                if node.get("type") == "entity":
                    relation = self.catalog.entity_relation(node.get("target"))
                    if relation and relation.get("target_table") in self.catalog.fact_tables():
                        time_filtered.add(relation["target_table"])
        having_sql = self._compile_filter_list(plan.get("having", []), dimension_fields, requested, params, date_bounds, having=True)
        lines = ["WITH " + ",\n".join(ctes), "SELECT " + ", ".join(select_sql), "FROM base_entities AS b"]
        lines.extend(main_joins)
        if where_sql:
            lines.append("WHERE " + where_sql)
        if group_dims:
            lines.append("GROUP BY " + ", ".join(f"b.{item}" for item in group_dims))
        if having_sql:
            lines.append("HAVING " + having_sql)
        if plan.get("order_by"):
            order_parts = []
            for item in plan["order_by"]:
                field = item["field"]
                if field not in set(selected):
                    raise SQLGenerationError("ORDER_FIELD_NOT_SELECTED", f"排序字段 {field} 未出现在安全输出中。")
                order_parts.append(f"{field} {item['direction'].upper()}")
            if ranking_mode and "pty_id" in selected and not any(item["field"] == "pty_id" for item in plan["order_by"]):
                order_parts.append("pty_id ASC")
            lines.append("ORDER BY " + ", ".join(order_parts))
        limit = plan.get("limit")
        if not aggregate_mode and not group_dims:
            limit = limit or int(self.cost_policy["default_detail_limit"])
        if limit:
            if limit > int(self.cost_policy["max_result_rows"]):
                raise SQLGenerationError("LIMIT_EXCEEDED", "Query Plan limit 超过成本上限。", limit)
            lines.append("LIMIT " + params.add(limit))
        return "\n".join(lines), selected, time_filtered

    def _dimension_bindings(
        self,
        plan: dict[str, Any],
        logical: LogicalPlan,
        bounds: tuple[str, str, int] | None,
        params: ParameterBag,
        excluded_dimensions: set[str] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[str], list[str], str | None]:
        excluded_dimensions = excluded_dimensions or set()
        needed = set(logical.dimensions) - excluded_dimensions
        for node in self._walk_filters(plan.get("filters", [])):
            if node.get("type") == "dimension":
                if node["target"] not in excluded_dimensions:
                    needed.add(node["target"])
        result: dict[str, dict[str, Any]] = {}
        joins: list[str] = []
        where: list[str] = []
        aliases: dict[str, str] = {"ads_cust_info_d": "c"}
        product_dimensions = [
            dimension for dimension in needed
            if self.catalog.dimensions.get(dimension, {}).get("source_table") == "dim_product"
        ]
        product_bridge: str | None = None
        if product_dimensions:
            candidates = {
                table
                for metric_id in logical.metric_order
                for table in (self.catalog.metrics[metric_id].get("source_tables", []) or [])
                if table in self.catalog.fact_tables()
                and self.catalog.verified_join("ads_cust_info_d", table)
                and self.catalog.verified_join(table, "dim_product")
            }
            if len(candidates) != 1:
                raise SQLGenerationError(
                    "SQL_UNSUPPORTED_COMBINATION",
                    "产品维度需要且只能确定一条 customer → fact → product verified join 路径。",
                    sorted(candidates),
                )
            product_bridge = next(iter(candidates))
            bridge_alias = "x_product"
            product_alias = "d_product"
            joins.append("JOIN " + product_bridge + f" AS {bridge_alias} ON " + self._verified_join_condition(
                "ads_cust_info_d", "c", product_bridge, bridge_alias,
            ))
            joins.append("JOIN dim_product AS d_product ON " + self._verified_join_condition(
                product_bridge, bridge_alias, "dim_product", product_alias,
            ))
            aliases[product_bridge] = bridge_alias
            aliases["dim_product"] = product_alias
            if bounds:
                time_field = self.catalog.tables[product_bridge].get("time", {}).get("field")
                if time_field:
                    where.append(f"{bridge_alias}.{time_field} BETWEEN {params.add(bounds[0])} AND {params.add(bounds[1])}")
        for dimension in needed:
            if dimension == "customer":
                continue
            meta = self.catalog.dimensions.get(dimension, {})
            source_table = meta.get("source_table")
            source_field = meta.get("source_field")
            if not source_table or not source_field:
                raise SQLGenerationError(
                    "SQL_UNSUPPORTED_COMBINATION",
                    f"维度 {dimension} 没有可执行的注册来源字段。",
                )
            if source_table == "ads_cust_info_d":
                alias = "c"
                route = ["ads_cust_info_d"]
            elif self.catalog.verified_join("ads_cust_info_d", source_table):
                alias = aliases.get(source_table, f"d_{source_table.removeprefix('dim_')}")
                if source_table not in aliases:
                    joins.append(f"JOIN {source_table} AS {alias} ON " + self._verified_join_condition(
                        "ads_cust_info_d", "c", source_table, alias,
                    ))
                    aliases[source_table] = alias
                route = ["ads_cust_info_d", source_table]
            elif source_table == "dim_product" and product_bridge:
                alias = aliases[source_table]
                route = ["ads_cust_info_d", product_bridge, "dim_product"]
            else:
                raise SQLGenerationError(
                    "SQL_UNSUPPORTED_COMBINATION",
                    f"维度 {dimension} 无法通过 verified join 转换到当前分析粒度。",
                )
            result[dimension] = {
                "source_table": source_table,
                "source_field": source_field,
                "expression": f"{alias}.{source_field}",
                "route": route,
            }
            logical.source_tables = sorted(set(logical.source_tables) | set(route))
            logical.dimension_routes[dimension] = {"path": route, "source_field": source_field}
        return result, joins, where, product_bridge

    def _scoped_relation_filters(
        self, nodes: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
        if any("logic" in node for node in nodes):
            return []
        dimensions = [node for node in nodes if node.get("type") == "dimension"]
        used: set[int] = set()
        groups: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        for relation_node in nodes:
            if (
                relation_node.get("type") != "entity"
                or relation_node.get("operator") not in {"exists", "not_exists"}
                or relation_node.get("value") is not None
            ):
                continue
            relation = self.catalog.entity_relation(relation_node.get("target"))
            if not relation:
                continue
            target_table = relation.get("target_table")
            scoped = []
            for dimension_node in dimensions:
                if id(dimension_node) in used:
                    continue
                meta = self.catalog.dimensions.get(dimension_node.get("target"), {})
                if (
                    meta.get("source_table")
                    and meta.get("source_table") != "ads_cust_info_d"
                    and self.catalog.verified_join(target_table, meta["source_table"])
                ):
                    scoped.append(dimension_node)
                    used.add(id(dimension_node))
            if scoped:
                groups.append((relation_node, scoped))
        return groups

    def _metric_scoped_dimension_filters(
        self, plan: dict[str, Any], logical: LogicalPlan,
    ) -> list[dict[str, Any]]:
        if plan.get("group_by") or not logical.requested_metrics:
            return []
        leaf_tables = []
        for metric_id in logical.requested_metrics:
            metric = self.catalog.metrics.get(metric_id, {})
            if metric.get("derived_from"):
                return []
            primary = self._primary_metric_table(metric)
            if not primary:
                return []
            leaf_tables.append(primary)
        result = []
        customer_table = self.mapping.get("subjects", {}).get("customer", {}).get("table")
        for node in plan.get("filters", []):
            if "logic" in node or node.get("type") != "dimension":
                continue
            meta = self.catalog.dimensions.get(node.get("target"), {})
            dimension_table = meta.get("source_table")
            if dimension_table and dimension_table != customer_table and all(
                self.catalog.verified_join(primary, dimension_table) for primary in leaf_tables
            ):
                result.append(node)
        return result

    def _metric_scoped_entity_filters(
        self, plan: dict[str, Any], logical: LogicalPlan,
    ) -> list[dict[str, Any]]:
        """Push a positive concrete entity into a same-grain metric fact.

        This turns "贵州茅台持仓市值" into a product-filtered holding
        aggregation instead of aggregating all holdings after a customer-level
        EXISTS test.  It is deliberately limited to non-derived, ungrouped
        metric queries whose requested metrics all share the relation fact.
        """
        if plan.get("intent") != "metric_query" or plan.get("group_by") or not logical.requested_metrics:
            return []
        requested = [self.catalog.metrics.get(item, {}) for item in logical.requested_metrics]
        if any(metric.get("derived_from") for metric in requested):
            return []
        primary_tables = {self._primary_metric_table(metric) for metric in requested}
        result = []
        for node in plan.get("filters", []):
            if (
                "logic" in node or node.get("type") != "entity"
                or node.get("operator") != "exists" or node.get("value") is None
            ):
                continue
            relation = self.catalog.entity_relation(node.get("target"))
            if relation and primary_tables == {relation.get("target_table")}:
                result.append(node)
        return result

    def _relation_dimension_predicate(
        self,
        relation_node: dict[str, Any],
        dimension_nodes: list[dict[str, Any]],
        params: ParameterBag,
        bounds: tuple[str, str, int] | None,
        logical: LogicalPlan,
    ) -> str:
        relation = self.catalog.entity_relation(relation_node.get("target"))
        if not relation or relation.get("grain_strategy") != "correlated_exists":
            raise SQLGenerationError(
                "UNSUPPORTED_ENTITY_RELATION",
                f"关系 {relation_node.get('target')} 不能承载 scoped dimension filter。",
            )
        table = relation["target_table"]
        key = relation["correlation_key"]
        aliases: dict[str, str] = {table: "e"}
        joins: list[str] = []
        clauses = [f"e.{key} = b.pty_id"]
        for index, node in enumerate(dimension_nodes, 1):
            meta = self.catalog.dimensions[node["target"]]
            dimension_table = meta["source_table"]
            alias = aliases.get(dimension_table)
            storage_value = self.catalog.storage_value(node["target"], node.get("value"))
            if dimension_table == table:
                clauses.append(self._operator(
                    f"e.{meta['source_field']}", node.get("operator"), storage_value, params,
                ))
            else:
                join = self.catalog.verified_join(table, dimension_table)
                if not join:
                    raise SQLGenerationError(
                        "SQL_UNSUPPORTED_COMBINATION",
                        f"缺少 verified join: {table} → {dimension_table}。",
                    )
                condition = join.get("condition", {})
                columns = {
                    join.get("left_table"): condition.get("left_column"),
                    join.get("right_table"): condition.get("right_column"),
                }
                fact_key, dimension_key = columns.get(table), columns.get(dimension_table)
                if not fact_key or not dimension_key:
                    raise SQLGenerationError("INVALID_JOIN_METADATA", "Verified join 缺少确定性字段映射。", join)
                alias = f"rd{index}"
                predicate = self._operator(
                    f"{alias}.{meta['source_field']}", node.get("operator"), storage_value, params,
                )
                clauses.append(
                    f"e.{fact_key} IN (SELECT DISTINCT {alias}.{dimension_key} "
                    f"FROM {dimension_table} AS {alias} WHERE {predicate})"
                )
            logical.source_tables = sorted(set(logical.source_tables) | {dimension_table})
        time_field = self.catalog.tables.get(table, {}).get("time", {}).get("field")
        if bounds and time_field:
            clauses.append(f"e.{time_field} BETWEEN {params.add(bounds[0])} AND {params.add(bounds[1])}")
        prefix = "NOT EXISTS" if relation_node.get("operator") == "not_exists" else "EXISTS"
        join_sql = (" " + " ".join(joins)) if joins else ""
        return f"{prefix} (SELECT e.{key} FROM {table} AS e{join_sql} WHERE " + " AND ".join(clauses) + ")"

    def _verified_join_condition(self, left_table: str, left_alias: str, right_table: str, right_alias: str) -> str:
        join = self.catalog.verified_join(left_table, right_table)
        if not join:
            raise SQLGenerationError(
                "SQL_UNSUPPORTED_COMBINATION",
                f"缺少 verified join: {left_table} → {right_table}。",
            )
        condition = join.get("condition", {})
        columns = {
            join.get("left_table"): condition.get("left_column"),
            join.get("right_table"): condition.get("right_column"),
        }
        if not columns.get(left_table) or not columns.get(right_table):
            raise SQLGenerationError("INVALID_JOIN_METADATA", "Verified join 缺少确定性字段映射。", join)
        return f"{left_alias}.{columns[left_table]} = {right_alias}.{columns[right_table]}"

    @staticmethod
    def _primary_metric_table(metric: dict[str, Any]) -> str | None:
        tables = metric.get("source_tables", []) or []
        return next((table for table in tables if table != "dim_product"), tables[0] if tables else None)

    @staticmethod
    def _aggregates_from_base_key(metric: dict[str, Any]) -> bool:
        aggregation = metric.get("aggregation") or {}
        return str(aggregation.get("outer", "")).lower() == "count_distinct"

    def _leaf_metric_cte(
        self,
        metric_id: str,
        metric: dict[str, Any],
        bounds: tuple[str, str, int] | None,
        params: ParameterBag,
        product_dimensions: dict[str, dict[str, Any]] | None = None,
        scoped_dimension_filters: list[dict[str, Any]] | None = None,
        scoped_entity_filters: list[dict[str, Any]] | None = None,
        restrict_to_base_entities: bool = False,
    ) -> tuple[str, set[str]]:
        product_dimensions = product_dimensions or {}
        scoped_dimension_filters = scoped_dimension_filters or []
        scoped_entity_filters = scoped_entity_filters or []
        tables = metric.get("source_tables", []) or []
        if not tables:
            raise SQLGenerationError("METRIC_SOURCE_MISSING", f"指标 {metric_id} 缺少来源表。")
        primary = next((table for table in tables if table != "dim_product"), tables[0])
        if primary not in self.catalog.tables:
            raise SQLGenerationError("UNKNOWN_METRIC_SOURCE", f"指标 {metric_id} 引用了未注册表 {primary}。")
        key = self.mapping["table_keys"].get(primary)
        if key != "pty_id":
            raise SQLGenerationError("UNSUPPORTED_METRIC_GRAIN", f"指标 {metric_id} 不能安全聚合到客户粒度。")
        alias = f"s_{metric_id}"
        joins: list[str] = []
        table_aliases = {primary: alias}
        if product_dimensions:
            join = self.catalog.verified_join(primary, "dim_product")
            if not join:
                raise SQLGenerationError("UNVERIFIED_METRIC_JOIN", f"指标 {metric_id} 需要未验证的产品 Join。")
            product_alias = f"p_{metric_id}"
            joins.append(
                f"JOIN dim_product AS {product_alias} ON "
                + self._verified_join_condition(primary, alias, "dim_product", product_alias)
            )
            table_aliases["dim_product"] = product_alias
        where: list[str] = []
        if restrict_to_base_entities:
            where.append(f"{alias}.pty_id IN (SELECT scoped_base.pty_id FROM base_entities AS scoped_base)")
        time_filtered: set[str] = set()
        time_meta = self.catalog.tables[primary].get("time", {})
        semantics = str(metric.get("time_semantics", ""))
        if bounds and time_meta.get("field") and semantics in {"snapshot", "daily_snapshot", "period_start", "period_end"}:
            start, end, _ = bounds
            selector = "MIN" if semantics == "period_start" else "MAX"
            effective = f"effective_{metric_id}"
            where.append(
                f"{alias}.{time_meta['field']} = (SELECT {selector}({effective}.{time_meta['field']}) "
                f"FROM {primary} AS {effective} WHERE {effective}.{time_meta['field']} BETWEEN "
                f"{params.add(start)} AND {params.add(end)})"
            )
            if primary in self.catalog.fact_tables():
                time_filtered.add(primary)
        elif bounds and time_meta.get("field"):
            start, end, _ = bounds
            where.append(f"{alias}.{time_meta['field']} BETWEEN {params.add(start)} AND {params.add(end)}")
            if primary in self.catalog.fact_tables():
                time_filtered.add(primary)
        for index, node in enumerate(scoped_dimension_filters, 1):
            dimension = self.catalog.dimensions[node["target"]]
            dimension_table = dimension["source_table"]
            join = self.catalog.verified_join(primary, dimension_table)
            if not join:
                raise SQLGenerationError(
                    "UNVERIFIED_METRIC_JOIN",
                    f"指标 {metric_id} 缺少到维度 {node['target']} 的 verified join。",
                )
            condition = join.get("condition", {})
            columns = {
                join.get("left_table"): condition.get("left_column"),
                join.get("right_table"): condition.get("right_column"),
            }
            primary_key, dimension_key = columns.get(primary), columns.get(dimension_table)
            if not primary_key or not dimension_key:
                raise SQLGenerationError("INVALID_JOIN_METADATA", "Verified join 缺少维度预过滤字段。", join)
            filter_alias = f"fd_{index}"
            predicate = self._operator(
                f"{filter_alias}.{dimension['source_field']}",
                node.get("operator"), self.catalog.storage_value(node["target"], node.get("value")), params,
            )
            where.append(
                f"{alias}.{primary_key} IN (SELECT DISTINCT {filter_alias}.{dimension_key} "
                f"FROM {dimension_table} AS {filter_alias} WHERE {predicate})"
            )
        for node in scoped_entity_filters:
            relation = self.catalog.entity_relation(node.get("target")) or {}
            if relation.get("target_table") != primary or not relation.get("entity_field"):
                raise SQLGenerationError(
                    "UNSUPPORTED_ENTITY_RELATION",
                    f"实体 {node.get('target')} 不能下推到指标事实 {primary}。",
                )
            where.append(self._operator(
                f"{alias}.{relation['entity_field']}", "eq", node.get("value"), params,
            ))
        constraints = metric.get("constraints", {}) or {}
        if constraints.get("required_time_range") and not bounds:
            raise SQLGenerationError("METRIC_TIME_REQUIRED", f"指标 {metric_id} 必须有明确时间范围。")
        internal_filter = (metric.get("filter") or "").strip()
        if internal_filter:
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'", internal_filter)
            if not match:
                raise SQLGenerationError("UNSAFE_METRIC_FILTER", f"指标 {metric_id} 的内置筛选无法安全参数化。")
            field, value = match.groups()
            owner = next((table for table in tables if field in self.catalog.table_columns(table)), None)
            if not owner:
                raise SQLGenerationError("UNKNOWN_METRIC_FILTER_COLUMN", f"指标 {metric_id} 的筛选字段 {field} 未注册。")
            if owner == "dim_product" and owner not in table_aliases:
                join = self.catalog.verified_join(primary, owner)
                condition = (join or {}).get("condition", {})
                columns = {
                    (join or {}).get("left_table"): condition.get("left_column"),
                    (join or {}).get("right_table"): condition.get("right_column"),
                }
                if not columns.get(primary) or not columns.get(owner):
                    raise SQLGenerationError("INVALID_JOIN_METADATA", "产品筛选缺少确定性字段映射。", join)
                where.append(
                    f"{alias}.{columns[primary]} IN (SELECT DISTINCT product_filter.{columns[owner]} "
                    f"FROM {owner} AS product_filter WHERE product_filter.{field} = {params.add(value)})"
                )
            else:
                where.append(f"{table_aliases[owner]}.{field} = {params.add(value)}")
        expression = self._metric_expression(metric_id, metric, alias, bounds, params)
        dimension_select = [
            f"{table_aliases['dim_product']}.{binding['source_field']} AS {dimension}"
            for dimension, binding in product_dimensions.items()
        ]
        select_items = [f"{alias}.pty_id AS pty_id", *dimension_select, f"{expression} AS {metric_id}"]
        sql = [f"metric_{metric_id} AS (", f"  SELECT {', '.join(select_items)}", f"  FROM {primary} AS {alias}"]
        sql.extend("  " + item for item in joins)
        if where:
            sql.append("  WHERE " + " AND ".join(where))
        group_items = [f"{alias}.pty_id", *(
            f"{table_aliases['dim_product']}.{binding['source_field']}"
            for binding in product_dimensions.values()
        )]
        sql.append("  GROUP BY " + ", ".join(group_items))
        sql.append(")")
        return "\n".join(sql), time_filtered

    def _metric_expression(self, metric_id: str, metric: dict[str, Any], alias: str, bounds: tuple[str, str, int] | None, params: ParameterBag) -> str:
        fields = metric.get("source_fields", []) or []
        raw_fields = {str(item).split(".")[-1] for item in fields}
        expression = (metric.get("expression") or "").strip()
        semantics = metric.get("time_semantics")
        if semantics in {"period_start", "period_end"}:
            if not bounds:
                raise SQLGenerationError("METRIC_TIME_REQUIRED", f"指标 {metric_id} 必须有时间范围。")
            asset = f"COALESCE({alias}.nm_tot_aset, 0) + COALESCE({alias}.fc_pur_aset, 0)"
            return f"SUM({asset})"
        if not expression:
            raise SQLGenerationError("METRIC_EXPRESSION_MISSING", f"指标 {metric_id} 缺少可编译表达式。")
        allowed_words = {"COALESCE", "SUM", "AVG", "COUNT", "DISTINCT", "NULLIF", "MIN", "MAX", "calendar_day_count"}
        identifiers = set(self.IDENTIFIER.findall(expression))
        unknown = identifiers - raw_fields - allowed_words
        if unknown:
            raise SQLGenerationError("METRIC_EXPRESSION_UNKNOWN_IDENTIFIER", f"指标 {metric_id} 表达式包含未注册标识符。", sorted(unknown))
        for field in sorted(raw_fields, key=len, reverse=True):
            expression = re.sub(rf"\b{re.escape(field)}\b", f"{alias}.{field}", expression)
        if "calendar_day_count" in expression:
            if not bounds:
                raise SQLGenerationError("METRIC_TIME_REQUIRED", f"指标 {metric_id} 需要日历天数。")
            expression = expression.replace("calendar_day_count", params.add(bounds[2]))
        aggregation = str((metric.get("aggregation") or {}).get("default", "none")).lower()
        if not self.AGGREGATE.search(expression):
            if aggregation == "sum":
                expression = f"SUM({expression})"
            elif aggregation == "avg":
                expression = f"AVG({expression})"
            elif aggregation == "min":
                expression = f"MIN({expression})"
            elif aggregation == "max":
                expression = f"MAX({expression})"
            elif aggregation == "count":
                expression = f"COUNT({expression})"
            elif aggregation == "count_distinct":
                expression = f"COUNT(DISTINCT {expression})"
            elif aggregation not in {"custom", "none", "first", "last"}:
                raise SQLGenerationError(
                    "UNSUPPORTED_METRIC_AGGREGATION",
                    f"指标 {metric_id} 的聚合类型 {aggregation} 尚无安全编译规则。",
                )
        return " ".join(expression.split())

    def _derived_metric_cte(
        self,
        metric_id: str,
        metric: dict[str, Any],
        dependencies: list[str],
        product_dimensions: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        product_dimensions = product_dimensions or {}
        expression = (metric.get("expression") or "").strip()
        unknown = set(self.IDENTIFIER.findall(expression)) - set(dependencies) - {"NULLIF"}
        if unknown:
            raise SQLGenerationError("DERIVED_EXPRESSION_UNKNOWN_IDENTIFIER", f"派生指标 {metric_id} 引用了未声明依赖。", sorted(unknown))
        for dependency in sorted(dependencies, key=len, reverse=True):
            expression = re.sub(rf"\b{re.escape(dependency)}\b", f"m_{dependency}.{dependency}", expression)
        first = dependencies[0]
        dimension_select = [f"m_{first}.{dimension} AS {dimension}" for dimension in product_dimensions]
        select_items = [f"m_{first}.pty_id AS pty_id", *dimension_select, f"{' '.join(expression.split())} AS {metric_id}"]
        lines = [f"metric_{metric_id} AS (", f"  SELECT {', '.join(select_items)}", f"  FROM metric_{first} AS m_{first}"]
        for dependency in dependencies[1:]:
            conditions = [f"m_{first}.pty_id = m_{dependency}.pty_id"]
            conditions.extend(f"m_{first}.{dimension} = m_{dependency}.{dimension}" for dimension in product_dimensions)
            lines.append(f"  LEFT JOIN metric_{dependency} AS m_{dependency} ON " + " AND ".join(conditions))
        lines.append(")")
        return "\n".join(lines)

    def _outer_metric(self, metric_id: str, aggregate: bool, base_key: str = "b.pty_id") -> str:
        ref = f"m_{metric_id}.{metric_id}"
        if not aggregate:
            return ref
        metric = self.catalog.metrics[metric_id]
        aggregation = metric.get("aggregation") or {}
        outer = str(aggregation.get("outer", aggregation.get("default", "sum"))).lower()
        if outer == "count_distinct":
            return f"COUNT(DISTINCT {base_key})"
        if outer in {"avg", "custom", "none"}:
            return f"AVG({ref})"
        if outer == "min":
            return f"MIN({ref})"
        if outer == "max":
            return f"MAX({ref})"
        if outer == "count":
            return f"COUNT({ref})"
        return f"SUM({ref})"

    def _compile_filter_list(self, nodes: list[dict[str, Any]], dimensions: dict[str, str], metrics: list[str], params: ParameterBag, bounds: tuple[str, str, int] | None, having: bool = False) -> str:
        return " AND ".join(self._compile_filter(node, dimensions, metrics, params, bounds, having) for node in nodes)

    def _compile_filter(self, node: dict[str, Any], dimensions: dict[str, str], metrics: list[str], params: ParameterBag, bounds: tuple[str, str, int] | None, having: bool) -> str:
        if "logic" in node:
            logic = node["logic"].upper()
            children = [self._compile_filter(item, dimensions, metrics, params, bounds, having) for item in node.get("conditions", [])]
            if logic == "NOT":
                return f"NOT ({children[0]})"
            return "(" + f" {logic} ".join(children) + ")"
        kind, target = node.get("type"), node.get("target")
        if kind == "dimension":
            if having:
                raise SQLGenerationError("DIMENSION_IN_HAVING", "维度筛选不能出现在 HAVING。")
            if target == "customer":
                left = "b.pty_id"
            elif target in dimensions:
                left = f"b.{target}"
            else:
                raise SQLGenerationError("FILTER_TARGET_UNAVAILABLE", f"维度 {target} 未被安全投影。")
        elif kind == "metric":
            if target not in metrics:
                raise SQLGenerationError("FILTER_METRIC_NOT_SELECTED", f"指标筛选 {target} 未列入 Query Plan metrics。")
            left = self._outer_metric(target, having)
        elif kind == "concept":
            raise SQLGenerationError(
                "SQL_UNSUPPORTED_COMBINATION",
                f"概念 {target} 必须在 Stage 4/5 展开为已验证维度筛选后才能编译。",
            )
        elif kind == "entity":
            if having:
                raise SQLGenerationError("ENTITY_IN_HAVING", "实体关系不能出现在 HAVING。")
            return self._entity_predicate(node, params, bounds)
        else:
            raise SQLGenerationError("UNKNOWN_FILTER_TYPE", f"不支持筛选类型 {kind}。")
        value = self.catalog.storage_value(target, node.get("value")) if kind == "dimension" else node.get("value")
        return self._operator(left, node.get("operator"), value, params)

    def _entity_predicate(self, node: dict[str, Any], params: ParameterBag, bounds: tuple[str, str, int] | None) -> str:
        relation = self.catalog.entity_relation(node.get("target"))
        if not relation:
            raise SQLGenerationError("UNKNOWN_ENTITY_RELATION", f"实体关系 {node.get('target')} 未注册执行映射。")
        operator = node.get("operator")
        value = node.get("value")
        dimension = relation.get("target_dimension")
        if dimension:
            if value is None:
                null_operator = "is_null" if operator == "not_exists" else "is_not_null"
                return self._operator(f"b.{dimension}", null_operator, None, params)
            comparison = "neq" if operator == "not_exists" else "eq" if operator == "exists" else operator
            return self._operator(f"b.{dimension}", comparison, value, params)
        table = relation["target_table"]
        key = relation["correlation_key"]
        clauses = [f"e.{key} = b.pty_id"]
        if value is not None:
            comparison = "eq" if operator in {"exists", "not_exists"} else operator
            clauses.append(self._operator(f"e.{relation['entity_field']}", comparison, value, params))
        time_field = self.catalog.tables.get(table, {}).get("time", {}).get("field")
        if bounds and time_field:
            clauses.append(f"e.{time_field} BETWEEN {params.add(bounds[0])} AND {params.add(bounds[1])}")
        prefix = "NOT EXISTS" if operator == "not_exists" else "EXISTS"
        return f"{prefix} (SELECT e.{key} FROM {table} AS e WHERE " + " AND ".join(clauses) + ")"

    def _operator(self, left: str, operator: str, value: Any, params: ParameterBag) -> str:
        symbols = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        if operator in symbols:
            return f"{left} {symbols[operator]} {params.add(value)}"
        if operator in {"is_null", "is_not_null"}:
            return f"{left} IS {'NOT ' if operator == 'is_not_null' else ''}NULL"
        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise SQLGenerationError("INVALID_FILTER_VALUE", f"{operator} 需要非空数组。")
            placeholders = ", ".join(params.add(item) for item in value)
            return f"{left} {'NOT ' if operator == 'not_in' else ''}IN ({placeholders})"
        if operator == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise SQLGenerationError("INVALID_FILTER_VALUE", "between 需要两个边界值。")
            return f"{left} BETWEEN {params.add(value[0])} AND {params.add(value[1])}"
        if operator in {"contains", "starts_with", "ends_with"}:
            raw = str(value)
            pattern = {"contains": f"%{raw}%", "starts_with": f"{raw}%", "ends_with": f"%{raw}"}[operator]
            return f"{left} LIKE {params.add(pattern)}"
        raise SQLGenerationError("UNSUPPORTED_OPERATOR", f"操作符 {operator} 尚无安全 SQL 映射。")

    @staticmethod
    def _date_bounds(time_range: dict[str, Any] | None) -> tuple[str, str, int] | None:
        if not time_range:
            return None
        kind = time_range["type"]
        if kind in {"start_of_period", "end_of_period"}:
            return SQLGenerator._date_bounds(time_range.get("period"))
        if kind == "quarter":
            year, quarter = int(time_range["year"]), int(time_range["quarter"])
            start_month = (quarter - 1) * 3 + 1
            start = date(year, start_month, 1)
            end_month = start_month + 2
            end = date(year, end_month, monthrange(year, end_month)[1])
        elif kind == "month":
            year, month = int(time_range["year"]), int(time_range["month"])
            start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        elif kind == "year":
            year = int(time_range["year"])
            start, end = date(year, 1, 1), date(year, 12, 31)
        elif kind == "date_range":
            start, end = date.fromisoformat(time_range["start"]), date.fromisoformat(time_range["end"])
        elif kind == "absolute_date":
            start = end = date.fromisoformat(time_range["date"])
        else:
            raise SQLGenerationError("NONDETERMINISTIC_TIME_RANGE", f"时间类型 {kind} 需要在 Stage 5 固化为绝对范围后才能执行。")
        if end < start:
            raise SQLGenerationError("INVALID_TIME_RANGE", "时间范围结束日期早于开始日期。")
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), (end - start).days + 1

    def _compile_time_series(
        self,
        plan: dict[str, Any],
        logical: LogicalPlan,
        bounds: tuple[str, str, int] | None,
        params: ParameterBag,
    ) -> tuple[str, list[str], set[str]]:
        buckets = plan.get("group_by", [])
        if len(buckets) != 1 or buckets[0] not in {"date", "month", "quarter"}:
            raise SQLGenerationError("SQL_UNSUPPORTED_COMBINATION", "趋势分析仅支持单一 date/month/quarter 时间桶。")
        if not bounds:
            raise SQLGenerationError("METRIC_TIME_REQUIRED", "趋势分析必须有明确时间范围。")
        bucket = buckets[0]
        selects: list[str] = []
        sources: set[str] = set()
        if len(logical.requested_metrics) != 1:
            raise SQLGenerationError("SQL_UNSUPPORTED_COMBINATION", "当前趋势分析要求指标共享同一事实来源。")
        metric_id = logical.requested_metrics[0]
        metric = self.catalog.metrics[metric_id]
        if metric.get("derived_from"):
            raise SQLGenerationError("SQL_UNSUPPORTED_COMBINATION", "派生指标趋势需要显式注册时间桶口径。")
        primary = self._primary_metric_table(metric)
        if not primary:
            raise SQLGenerationError("METRIC_SOURCE_MISSING", f"指标 {metric_id} 缺少来源表。")
        time_field = self.catalog.tables[primary].get("time", {}).get("field")
        if not time_field:
            raise SQLGenerationError("SQL_UNSUPPORTED_COMBINATION", f"指标 {metric_id} 来源没有时间字段。")
        alias = "ts"
        if bucket == "date":
            bucket_expression = f"{alias}.{time_field}"
        elif bucket == "month":
            bucket_expression = f"SUBSTRING({alias}.{time_field}, {params.add(1)}, {params.add(6)})"
        else:
            bucket_expression = (
                f"CONCAT(SUBSTRING({alias}.{time_field}, {params.add(1)}, {params.add(4)}), {params.add('Q')}, "
                f"QUARTER(STR_TO_DATE({alias}.{time_field}, {params.add('%Y%m%d')})))"
            )
        expression = self._metric_expression(metric_id, metric, alias, bounds, params)
        where = [f"{alias}.{time_field} BETWEEN {params.add(bounds[0])} AND {params.add(bounds[1])}"]
        internal_filter = (metric.get("filter") or "").strip()
        if internal_filter:
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'", internal_filter)
            if not match:
                raise SQLGenerationError("UNSAFE_METRIC_FILTER", f"指标 {metric_id} 的内置筛选无法安全参数化。")
            field, value = match.groups()
            owner = next((table for table in metric.get("source_tables", []) if field in self.catalog.table_columns(table)), None)
            if owner == primary:
                where.append(f"{alias}.{field} = {params.add(value)}")
            elif owner == "dim_product":
                join = self.catalog.verified_join(primary, owner)
                condition = (join or {}).get("condition", {})
                columns = {(join or {}).get("left_table"): condition.get("left_column"), (join or {}).get("right_table"): condition.get("right_column")}
                where.append(
                    f"{alias}.{columns[primary]} IN (SELECT DISTINCT ts_product.{columns[owner]} FROM {owner} AS ts_product "
                    f"WHERE ts_product.{field} = {params.add(value)})"
                )
        selects.extend([f"{bucket_expression} AS {bucket}", f"{expression} AS {metric_id}"])
        sql = [f"SELECT {', '.join(selects)}", f"FROM {primary} AS {alias}", "WHERE " + " AND ".join(where), f"GROUP BY {bucket_expression}", f"ORDER BY {bucket} ASC"]
        sources.add(primary)
        if "dim_product" in (metric.get("source_tables", []) or []):
            sources.add("dim_product")
        logical.source_tables = sorted(set(logical.source_tables) | sources)
        return "\n".join(sql), [bucket, metric_id], {primary}

    @classmethod
    def _walk_filters(cls, nodes: list[dict[str, Any]]):
        for node in nodes:
            if "logic" in node:
                yield from cls._walk_filters(node.get("conditions", []))
            else:
                yield node
