from __future__ import annotations

from typing import Any

from query_plan.canonicalizer import (
    SEMANTIC_FIELDS,
    CanonicalizationContext,
    canonicalize_query_plan,
)


IGNORED_ROOT_FIELDS = {"version", "confidence", "context"}
IGNORED_PRESENTATION_FIELDS = {"output"}
CORE_SEMANTIC_FIELDS = {
    "status", "intent", "subject", "metrics", "dimensions", "filters",
    "entities", "time_range", "group_by", "having", "order_by", "limit",
}


def compare_plan_semantics(
    expected: dict[str, Any],
    actual: dict[str, Any],
    context: CanonicalizationContext | None = None,
) -> dict[str, Any]:
    """Compare canonical business semantics and explain every ignored/different field."""

    expected_canonical = canonicalize_query_plan(expected, context)
    actual_canonical = canonicalize_query_plan(actual, context)
    differences = []
    ignored = []
    compared_fields = []
    for field in SEMANTIC_FIELDS:
        if field in IGNORED_PRESENTATION_FIELDS:
            if expected_canonical.get(field) != actual_canonical.get(field):
                ignored.append({
                    "path": field,
                    "reason": "presentation_contract_not_execution_semantics",
                    "expected": expected_canonical.get(field),
                    "actual": actual_canonical.get(field),
                })
            continue
        # Core business semantics are always compared. A missing Gold field is
        # canonicalized to its schema-empty value; it must not hide an extra
        # metric, filter, entity, time range, intent, status, or ordering rule.
        if field not in expected and field not in CORE_SEMANTIC_FIELDS:
            if field in actual and actual_canonical.get(field) not in (None, [], {}):
                ignored.append({
                    "path": field, "reason": "gold_missing_field",
                    "actual": actual_canonical.get(field),
                })
            continue
        compared_fields.append(field)
        if expected_canonical.get(field) != actual_canonical.get(field):
            differences.append({
                "path": field,
                "expected": expected_canonical.get(field),
                "actual": actual_canonical.get(field),
                "kind": _difference_kind(field, expected_canonical.get(field), actual_canonical.get(field)),
            })

    for field in IGNORED_ROOT_FIELDS:
        if expected.get(field) != actual.get(field):
            ignored.append({"path": field, "reason": "comparison_policy_ignored"})
    if expected.get("output") != actual.get("output") and expected_canonical.get("output") == actual_canonical.get("output"):
        ignored.append({"path": "output.presentation", "reason": "format_or_explanation_only"})
    if expected.get("filters") != actual.get("filters") and expected_canonical.get("filters") == actual_canonical.get("filters"):
        ignored.append({"path": "filters", "reason": "ids_source_confidence_order_or_equivalent_expansion"})
    if expected.get("entities") != actual.get("entities") and expected_canonical.get("entities") == actual_canonical.get("entities"):
        ignored.append({"path": "entities", "reason": "surface_name_attributes_or_order_only"})

    return {
        "equivalent": not differences,
        "compared_fields": compared_fields,
        "differences": differences,
        "semantic_differences": differences,
        "ignored_differences": ignored,
        "expected_canonical": expected_canonical,
        "actual_canonical": actual_canonical,
    }


def _difference_kind(field: str, expected: Any, actual: Any) -> str:
    if field == "entities":
        return "ENTITY_RESOLUTION_OR_ID_MISMATCH"
    if field == "time_range":
        return "TIME_SEMANTIC_MISMATCH"
    if field == "filters":
        return "FILTER_SEMANTIC_MISMATCH"
    if field == "status":
        return "STATUS_MISMATCH"
    if field == "intent":
        return "INTENT_MISMATCH"
    return f"{field.upper()}_MISMATCH"
