"""Deterministic semantic canonicalization for Stage 4 Query Plans.

The canonical form is for comparison and audit. It does not replace the
validated production plan and never consults a query string or benchmark ID.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
import json
import re
from typing import Any, TypedDict


SEMANTIC_FIELDS = (
    "status", "intent", "subject", "metrics", "dimensions", "filters",
    "entities", "time_range", "group_by", "having", "order_by", "limit",
    "output", "assumptions", "ambiguities",
)


class CanonicalQueryPlan(TypedDict):
    """Stable comparison contract; never used as an execution-plan substitute."""

    status: Any
    intent: Any
    subject: Any
    metrics: list[Any]
    dimensions: list[Any]
    filters: Any
    entities: list[dict[str, Any]]
    time_range: Any
    group_by: list[Any]
    having: Any
    order_by: list[dict[str, Any]]
    limit: Any
    output: dict[str, Any]
    assumptions: list[dict[str, Any]]
    ambiguities: list[dict[str, Any]]

OPERATOR_ALIASES = {
    "=": "eq", "==": "eq", "eq": "eq",
    "!=": "neq", "<>": "neq", "neq": "neq",
    ">": "gt", "gt": "gt", ">=": "gte", "gte": "gte",
    "<": "lt", "lt": "lt", "<=": "lte", "lte": "lte",
    "in": "in", "not_in": "not_in", "between": "between",
    "contains": "contains", "starts_with": "starts_with", "ends_with": "ends_with",
    "exists": "exists", "not_exists": "not_exists",
    "is_null": "is_null", "is_not_null": "is_not_null",
}


@dataclass(frozen=True)
class CanonicalizationContext:
    ratio_metrics: frozenset[str] = frozenset()
    concept_mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    dimension_value_aliases: dict[str, dict[str, Any]] = field(default_factory=dict)


def build_canonicalization_context(
    metrics: dict[str, Any],
    dimensions: dict[str, Any],
    dictionary: dict[str, Any],
) -> CanonicalizationContext:
    """Build immutable-by-convention comparison metadata outside the pure transform."""

    ratio_metrics = {
        metric_id for metric_id, definition in metrics.items()
        if metric_id.endswith("_ratio")
        or definition.get("explain", {}).get("unit") in {"比例", "百分比", "%"}
    }
    aliases: dict[str, dict[str, Any]] = {}
    for dimension_id, definition in dimensions.items():
        mapping: dict[str, Any] = {}
        for code, display in (definition.get("enum") or {}).items():
            mapping[_text_key(code)] = code
            mapping[_text_key(display)] = code
        aliases[dimension_id] = mapping

    concept_mappings: dict[str, dict[str, Any]] = {}
    for concept_id, definition in dictionary.items():
        dimension = definition.get("dimension")
        if not dimension:
            continue
        raw_values = definition.get("value_mapping") or definition.get("values")
        if raw_values is None and definition.get("includes"):
            raw_values = [item.get("code") for item in definition["includes"] if item.get("code") is not None]
        values = list(raw_values or [])
        if not values:
            continue
        concept_mappings[concept_id] = {"dimension": dimension, "values": values}
        value_aliases = aliases.setdefault(dimension, {})
        for value in values:
            value_aliases[_text_key(value)] = value
        if len(values) == 1:
            for surface in [definition.get("name"), *(definition.get("aliases") or [])]:
                if surface:
                    value_aliases[_text_key(surface)] = values[0]
        for item in definition.get("includes") or []:
            if item.get("code") is not None and item.get("value"):
                value_aliases[_text_key(item["value"])] = item["code"]
    return CanonicalizationContext(
        ratio_metrics=frozenset(ratio_metrics),
        concept_mappings=concept_mappings,
        dimension_value_aliases=aliases,
    )


def _text_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _number(value: Any, ratio: bool = False) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        compact = value.strip()
        if ratio and compact.endswith("%"):
            try:
                return _number(float(compact[:-1]) / 100)
            except ValueError:
                return compact
        try:
            value = float(compact)
        except ValueError:
            return compact
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, 12)
    return value


def _canonical_value(
    value: Any,
    target: str | None,
    context: CanonicalizationContext,
    *,
    unordered_list: bool = False,
) -> Any:
    if isinstance(value, list):
        normalized = [
            _canonical_value(item, target, context, unordered_list=unordered_list)
            for item in value
        ]
        return sorted(normalized, key=_stable_key) if unordered_list else normalized
    if isinstance(value, dict):
        return {
            key: _canonical_value(item, target, context, unordered_list=unordered_list)
            for key, item in sorted(value.items())
        }
    mapping = context.dimension_value_aliases.get(target or "", {})
    mapped = mapping.get(_text_key(value))
    if mapped is not None:
        value = mapped
    return _number(value, ratio=target in context.ratio_metrics)


def _leaf(node: dict[str, Any], context: CanonicalizationContext) -> dict[str, Any]:
    filter_type = node.get("type")
    target = node.get("target")
    operator = OPERATOR_ALIASES.get(str(node.get("operator", "")).lower(), node.get("operator"))
    value = node.get("value")

    if filter_type == "concept" and target in context.concept_mappings:
        mapping = context.concept_mappings[target]
        values = [_canonical_value(item, mapping["dimension"], context) for item in mapping["values"]]
        positive = not (operator == "neq" or (operator == "eq" and value is False))
        filter_type = "dimension"
        target = mapping["dimension"]
        operator = "eq" if len(values) == 1 else "in"
        value = values[0] if len(values) == 1 else sorted(values, key=_stable_key)
        if not positive:
            operator = "neq" if operator == "eq" else "not_in"
    else:
        # Membership values are sets. Positional values such as BETWEEN bounds
        # are ordered business semantics and must never be reordered.
        value = _canonical_value(
            value,
            target,
            context,
            unordered_list=operator in {"in", "not_in"},
        )

    result = {"type": filter_type, "target": target, "operator": operator}
    if operator not in {"exists", "not_exists", "is_null", "is_not_null"} or value is not None:
        result["value"] = value
    if operator in {"neq", "not_in", "not_exists", "is_not_null"}:
        positive = {"neq": "eq", "not_in": "in", "not_exists": "exists", "is_not_null": "is_null"}[operator]
        child = dict(result)
        child["operator"] = positive
        return {"logic": "not", "conditions": [child]}
    return result


def canonicalize_filter(node: dict[str, Any], context: CanonicalizationContext) -> dict[str, Any]:
    if "logic" not in node:
        return _leaf(node, context)
    logic = str(node.get("logic", "")).lower()
    children = [canonicalize_filter(item, context) for item in node.get("conditions") or []]
    if logic in {"and", "or"}:
        flattened: list[dict[str, Any]] = []
        for child in children:
            if child.get("logic") == logic:
                flattened.extend(child.get("conditions") or [])
            else:
                flattened.append(child)
        children = sorted(flattened, key=_stable_key)
    return {"logic": logic, "conditions": children}


def _canonical_filter_set(nodes: Any, context: CanonicalizationContext) -> Any:
    items = [canonicalize_filter(item, context) for item in (nodes or [])]
    if not items:
        return []
    if len(items) == 1:
        return items[0]
    return canonicalize_filter({"logic": "and", "conditions": items}, context)


def _implied_dimensions(nodes: Any, context: CanonicalizationContext) -> set[str]:
    result: set[str] = set()
    for node in nodes or []:
        if "logic" in node:
            result |= _implied_dimensions(node.get("conditions"), context)
        elif node.get("type") == "concept" and node.get("target") in context.concept_mappings:
            result.add(context.concept_mappings[node["target"]]["dimension"])
    return result


def _canonical_time(value: Any) -> Any:
    if not isinstance(value, dict) or not value:
        return None
    kind = value.get("type")
    if kind in {"start_of_period", "end_of_period"}:
        return {"type": kind, "period": _canonical_time(value.get("period"))}
    if kind == "quarter" and value.get("year") and value.get("quarter"):
        year, quarter = int(value["year"]), int(value["quarter"])
        month = (quarter - 1) * 3 + 1
        return {
            "type": "interval", "start": date(year, month, 1).isoformat(),
            "end": date(year, month + 2, calendar.monthrange(year, month + 2)[1]).isoformat(),
            "granularity": "quarter",
        }
    if kind == "month" and value.get("year") and value.get("month"):
        year, month = int(value["year"]), int(value["month"])
        return {
            "type": "interval", "start": date(year, month, 1).isoformat(),
            "end": date(year, month, calendar.monthrange(year, month)[1]).isoformat(),
            "granularity": "month",
        }
    if kind == "year" and value.get("year"):
        year = int(value["year"])
        return {"type": "interval", "start": f"{year:04d}-01-01", "end": f"{year:04d}-12-31", "granularity": "year"}
    if kind == "absolute_date" and value.get("date"):
        return {"type": "interval", "start": value["date"], "end": value["date"], "granularity": "day"}
    if kind == "date_range":
        start, end = value.get("start", value.get("start_date")), value.get("end", value.get("end_date"))
        granularity = "day"
        if start and end:
            try:
                start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
                quarter = (start_date.month - 1) // 3 + 1
                quarter_start_month = (quarter - 1) * 3 + 1
                quarter_end_month = quarter_start_month + 2
                if (
                    start_date == date(start_date.year, quarter_start_month, 1)
                    and end_date == date(start_date.year, quarter_end_month, calendar.monthrange(start_date.year, quarter_end_month)[1])
                ):
                    granularity = "quarter"
            except ValueError:
                pass
        return {"type": "interval", "start": start, "end": end, "granularity": granularity}
    return {key: value[key] for key in sorted(value) if value[key] is not None and key != "raw_expression"}


def _canonical_entity(entity: dict[str, Any]) -> dict[str, Any]:
    status = entity.get("resolution_status", entity.get("status"))
    entity_type = entity.get("entity_type")
    resolved = entity.get("resolved") or {}
    if status == "resolved":
        identifier = resolved.get("id", entity.get("id"))
        return {"entity_type": entity_type, "resolution_status": "resolved", "id": str(identifier)}
    if status == "ambiguous":
        candidates = entity.get("candidates") or []
        ids = sorted(str(item.get("id")) for item in candidates if item.get("id") is not None)
        return {"entity_type": entity_type, "resolution_status": "ambiguous", "candidate_ids": ids}
    return {
        "entity_type": entity_type, "resolution_status": status or "not_found",
        "surface": _text_key(entity.get("surface")),
    }


def _canonical_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in ("mode", "include_details") if key in value}


def _canonical_assumptions(values: Any) -> list[dict[str, Any]]:
    output = [
        {key: item.get(key) for key in ("description", "source", "review_required") if key in item}
        for item in (values or []) if isinstance(item, dict)
    ]
    return sorted(output, key=_stable_key)


def _canonical_ambiguities(values: Any) -> list[dict[str, Any]]:
    output = []
    for item in values or []:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates", item.get("options", [])) or []
        candidate_ids = []
        for candidate in candidates:
            if isinstance(candidate, dict):
                candidate_ids.append(candidate.get("id") or candidate.get("metric_id") or candidate.get("dimension_id") or candidate.get("value"))
            else:
                candidate_ids.append(candidate)
        output.append({"type": item.get("type"), "candidate_ids": sorted((str(x) for x in candidate_ids if x is not None))})
    return sorted(output, key=_stable_key)


def canonicalize_query_plan(
    plan: dict[str, Any] | None,
    context: CanonicalizationContext | None = None,
) -> CanonicalQueryPlan:
    """Return a deterministic semantic form without mutating the input plan."""

    source = plan or {}
    context = context or CanonicalizationContext()
    filters = source.get("filters") or []
    having = source.get("having") or []
    dimensions = set(source.get("dimensions") or [])
    dimensions |= _implied_dimensions(filters, context)
    dimensions |= _implied_dimensions(having, context)
    entities = sorted((_canonical_entity(item) for item in source.get("entities") or []), key=_stable_key)
    order_by = [
        {"field": item.get("field"), "direction": str(item.get("direction", "")).lower()}
        for item in source.get("order_by") or []
    ]
    return {
        "status": source.get("status"),
        "intent": source.get("intent"),
        "subject": source.get("subject"),
        "metrics": sorted(set(source.get("metrics") or [])),
        "dimensions": sorted(dimensions),
        "filters": _canonical_filter_set(filters, context),
        "entities": entities,
        "time_range": _canonical_time(source.get("time_range")),
        "group_by": sorted(set(source.get("group_by") or [])),
        "having": _canonical_filter_set(having, context),
        "order_by": order_by,
        "limit": _number(source.get("limit")),
        "output": _canonical_output(source.get("output")),
        "assumptions": _canonical_assumptions(source.get("assumptions")),
        "ambiguities": _canonical_ambiguities(source.get("ambiguities")),
    }
