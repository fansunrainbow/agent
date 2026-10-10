from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .catalog import MetadataCatalog


class LogicalPlanningError(ValueError):
    def __init__(self, code: str, message: str, evidence: Any | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence


@dataclass
class LogicalPlan:
    subject: str
    base_table: str
    key: str
    requested_metrics: list[str]
    metric_order: list[str]
    dimensions: list[str]
    filters: list[dict[str, Any]]
    time_range: dict[str, Any] | None
    joins: list[dict[str, Any]] = field(default_factory=list)
    source_tables: list[str] = field(default_factory=list)
    grain: str = "customer"
    metric_grains: dict[str, list[str]] = field(default_factory=dict)
    dimension_routes: dict[str, dict[str, Any]] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)
    having: list[dict[str, Any]] = field(default_factory=list)
    order_by: list[dict[str, Any]] = field(default_factory=list)
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = deepcopy(self.__dict__)
        data.update({
            "required_metrics": list(self.requested_metrics),
            "required_dimensions": list(self.dimensions),
            "required_tables": list(self.source_tables),
            "required_joins": deepcopy(self.joins),
            "required_filters": deepcopy(self.filters),
            "time_filters": deepcopy(self.time_range),
            "output_grain": list(self.group_by) if self.group_by else [self.grain],
        })
        return data


class LogicalPlanner:
    """Builds a registry-backed logical plan; it never consumes natural language."""

    def __init__(self, catalog: MetadataCatalog, mapping: dict[str, Any]):
        self.catalog = catalog
        self.mapping = mapping

    def _metric_dependencies(self, metric_id: str, ordered: list[str], visiting: set[str]) -> None:
        if metric_id in ordered:
            return
        if metric_id in visiting:
            raise LogicalPlanningError("METRIC_DEPENDENCY_CYCLE", f"指标 {metric_id} 的依赖存在环。")
        metric = self.catalog.metrics.get(metric_id)
        if metric is None:
            raise LogicalPlanningError("UNKNOWN_METRIC", f"指标 {metric_id} 未注册。")
        visiting.add(metric_id)
        for dependency in metric.get("derived_from", []) or []:
            self._metric_dependencies(dependency, ordered, visiting)
        visiting.remove(metric_id)
        ordered.append(metric_id)

    def build(self, plan: dict[str, Any]) -> LogicalPlan:
        subject = plan["subject"]
        subject_meta = self.mapping.get("subjects", {}).get(subject)
        if not subject_meta:
            raise LogicalPlanningError("UNSUPPORTED_SUBJECT", f"Subject {subject} 尚无执行映射。")
        dimensions = list(dict.fromkeys(plan.get("dimensions", []) + plan.get("group_by", [])))
        for dimension in dimensions:
            if dimension not in self.catalog.dimensions:
                raise LogicalPlanningError("UNKNOWN_DIMENSION", f"维度 {dimension} 未注册。")
        metric_order: list[str] = []
        requested = list(dict.fromkeys(plan.get("metrics", [])))
        filter_metrics = [item.get("target") for item in self._walk_filters(plan.get("filters", []) + plan.get("having", [])) if item.get("type") == "metric"]
        order_metrics = [item.get("field") for item in plan.get("order_by", []) if item.get("field") in self.catalog.metrics]
        for metric_id in requested + filter_metrics + order_metrics:
            if metric_id:
                self._metric_dependencies(metric_id, metric_order, set())
        if not metric_order and not dimensions and not plan.get("filters") and not plan.get("entities"):
            raise LogicalPlanningError("EMPTY_EXECUTABLE_PLAN", "Query Plan 不含可执行的指标、维度、实体或筛选条件。")
        sources = {subject_meta["table"]}
        joins: list[dict[str, Any]] = []
        for metric_id in metric_order:
            sources.update(self.catalog.metrics[metric_id].get("source_tables", []) or [])
            metric_grain = self.catalog.metrics[metric_id].get("grain", []) or []
            if subject in {"customer", "branch"} and not ({"customer", "customer_group"} & set(metric_grain)):
                raise LogicalPlanningError(
                    "SQL_UNSUPPORTED_COMBINATION",
                    f"指标 {metric_id} 无法安全转换到客户/机构分析粒度。",
                    {"subject": subject, "metric_grain": metric_grain},
                )
        for node in self._walk_filters(plan.get("filters", [])):
            if node.get("type") == "entity":
                relation_id = node.get("target")
                relation = self.catalog.entity_relation(relation_id)
                if not relation:
                    raise LogicalPlanningError(
                        "UNKNOWN_ENTITY_RELATION",
                        f"实体关系 {relation_id} 未注册或未启用。",
                    )
                join = self.catalog.verified_join_by_id(relation.get("verified_join"))
                if not join:
                    raise LogicalPlanningError(
                        "UNVERIFIED_ENTITY_RELATION",
                        f"实体关系 {relation_id} 未绑定 verified join。",
                        relation,
                    )
                pair = {join.get("left_table"), join.get("right_table")}
                expected_pair = {relation.get("source_table"), relation.get("target_table")}
                if pair != expected_pair:
                    raise LogicalPlanningError(
                        "INVALID_ENTITY_RELATION_PATH",
                        f"实体关系 {relation_id} 的表路径与 verified join 不一致。",
                        {"relation": relation, "join": join},
                    )
                strategy = relation.get("grain_strategy")
                if strategy not in {"correlated_exists", "verified_dimension_join"}:
                    raise LogicalPlanningError(
                        "RELATION_GRAIN_AMPLIFICATION",
                        f"实体关系 {relation_id} 没有可证明安全的粒度策略。",
                        relation,
                    )
                target_table = relation.get("target_table")
                if target_table:
                    sources.add(target_table)
                target_dimension = relation.get("target_dimension")
                if target_dimension:
                    if target_dimension not in self.catalog.dimensions:
                        raise LogicalPlanningError(
                            "UNKNOWN_DIMENSION",
                            f"实体关系 {relation_id} 引用了未注册维度 {target_dimension}。",
                        )
                    if target_dimension not in dimensions:
                        dimensions.append(target_dimension)
        fact_sources = sorted(sources & self.catalog.fact_tables())
        for index, left in enumerate(fact_sources):
            for right in fact_sources[index + 1:]:
                joins.append({"left": left, "right": right, "key": "pty_id", "preaggregated": True})
        return LogicalPlan(
            subject=subject, base_table=subject_meta["table"], key=subject_meta["key"],
            requested_metrics=requested, metric_order=metric_order, dimensions=dimensions,
            filters=deepcopy(plan.get("filters", [])), time_range=deepcopy(plan.get("time_range")),
            joins=joins, source_tables=sorted(sources),
            grain="customer" if subject in {"customer", "branch"} else subject,
            metric_grains={metric_id: list(self.catalog.metrics[metric_id].get("grain", []) or []) for metric_id in metric_order},
            group_by=deepcopy(plan.get("group_by", [])), having=deepcopy(plan.get("having", [])),
            order_by=deepcopy(plan.get("order_by", [])), limit=plan.get("limit"),
        )

    @classmethod
    def _walk_filters(cls, nodes: list[dict[str, Any]]):
        for node in nodes:
            if "logic" in node:
                yield from cls._walk_filters(node.get("conditions", []))
            else:
                yield node
