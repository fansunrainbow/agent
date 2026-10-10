from pathlib import Path
from datetime import date
import json
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry, Resource


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from query_plan.models import QueryPlan

METADATA_DIR = ROOT / "metadata"
SCHEMA_DIR = ROOT / "query_plan" / "schema"
EXAMPLE_DIR = ROOT / "query_plan" / "examples"


FILES = {
    "intents": METADATA_DIR / "intent_registry.yaml",
    "operators": METADATA_DIR / "operator_registry.yaml",
    "time_semantics": METADATA_DIR / "time_semantics.yaml",
    "capabilities": METADATA_DIR / "query_capabilities.yaml",
    "confidence": METADATA_DIR / "query_plan_confidence.yaml",

    "metrics": METADATA_DIR / "metrics.yaml",
    "metric_constraints": METADATA_DIR / "metric_constraints.yaml",
    "dimensions": METADATA_DIR / "dimensions.yaml",
    "dictionary": METADATA_DIR / "business_dictionary.yaml",
    "entities": METADATA_DIR / "entity_rules.yaml",
    "joins": METADATA_DIR / "joins.yaml",
    "value_mappings": METADATA_DIR / "value_mappings.yaml",

    "schema": SCHEMA_DIR / "query_plan.schema.json",
    "filter_schema": SCHEMA_DIR / "filter.schema.json",
    "time_schema": SCHEMA_DIR / "time_range.schema.json",
    "entity_schema": SCHEMA_DIR / "entity_ref.schema.json",
}


# ============================================================
# 基础读取
# ============================================================

def load_yaml(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Registry 提取
# ============================================================

def extract_keys(data, possible_keys):
    for key in possible_keys:
        value = data.get(key)

        if isinstance(value, dict):
            return set(value.keys())

        if isinstance(value, list):
            result = set()

            for item in value:
                if isinstance(item, str):
                    result.add(item)

                elif isinstance(item, dict):
                    for candidate in (
                        "id",
                        "metric_id",
                        "dimension_id",
                        "name",
                    ):
                        if candidate in item:
                            result.add(str(item[candidate]))
                            break

            return result

    return set()


def extract_metric_ids(metrics_data):
    return extract_keys(metrics_data, ["metrics"])


def extract_dimension_ids(dimensions_data):
    return extract_keys(dimensions_data, ["dimensions"])


def extract_concept_ids(dictionary_data):
    return extract_keys(
        dictionary_data,
        ["dictionary", "concepts"]
    )


def extract_intent_ids(intent_data):
    return extract_keys(intent_data, ["intents"])


def extract_operator_ids(operator_data):
    result = set()

    operators = operator_data.get("operators", {})
    logic_operators = operator_data.get("logic_operators", {})

    if isinstance(operators, dict):
        result.update(operators.keys())

    if isinstance(logic_operators, dict):
        result.update(logic_operators.keys())

    return result


def extract_capability_ids(capability_data):
    return extract_keys(
        capability_data,
        ["capabilities"]
    )


def extract_time_types(time_data):
    return extract_keys(
        time_data,
        ["time_types"]
    )


# ============================================================
# 统一错误结构
# ============================================================

def make_error(code, path, value=None, message=None):
    item = {
        "code": code,
        "path": path,
    }

    if value is not None:
        item["value"] = value

    if message:
        item["message"] = message

    return item


def make_warning(code, path, value=None, message=None):
    item = {
        "code": code,
        "path": path,
    }

    if value is not None:
        item["value"] = value

    if message:
        item["message"] = message

    return item


# ============================================================
# JSON Schema Registry
# ============================================================

def build_schema_registry():
    registry = Registry()

    schema_files = [
        FILES["schema"],
        FILES["filter_schema"],
        FILES["time_schema"],
        FILES["entity_schema"],
    ]

    for path in schema_files:
        schema = load_json(path)

        schema_id = schema.get("$id")

        if not schema_id:
            raise ValueError(
                f"Schema 缺少 $id: {path}"
            )

        resource = Resource.from_contents(schema)

        registry = registry.with_resource(
            schema_id,
            resource,
        )

    return registry


# ============================================================
# Structural Validation
# ============================================================

def validate_structure(plan, schema_path):
    schema = load_json(schema_path)

    registry = build_schema_registry()

    validator = Draft202012Validator(
        schema=schema,
        registry=registry,
        format_checker=FormatChecker(),
    )

    errors = []

    for error in sorted(
        validator.iter_errors(plan),
        key=lambda e: list(e.absolute_path)
    ):
        path = ".".join(
            str(x) for x in error.absolute_path
        )

        if not path:
            path = "$"

        absolute_path = list(error.absolute_path)
        code = "STRUCTURAL_ERROR"

        nested_errors = list(error.context)
        for nested in list(nested_errors):
            nested_errors.extend(nested.context)
        has_operator_error = any(
            item.absolute_path and list(item.absolute_path)[-1] == "operator"
            for item in nested_errors
        )

        if (absolute_path and absolute_path[-1] == "operator") or has_operator_error:
            code = "UNKNOWN_OPERATOR"
        elif absolute_path == ["intent"]:
            code = "UNKNOWN_INTENT"
        elif absolute_path and absolute_path[0] in {"filters", "having"}:
            code = "INVALID_FILTER"
        elif absolute_path and absolute_path[0] == "time_range":
            code = "INVALID_TIME_RANGE"
        elif absolute_path and absolute_path[0] == "limit":
            code = "INVALID_LIMIT"

        errors.append(
            make_error(
                code=code,
                path=path,
                message=error.message,
            )
        )

    return errors


# ============================================================
# Filter 遍历
# ============================================================

def walk_filter_nodes(node):
    if not isinstance(node, dict):
        return

    if "logic" in node:
        for child in node.get("conditions", []):
            yield from walk_filter_nodes(child)
    else:
        yield node


def walk_all_filters(plan):
    for index, node in enumerate(
        plan.get("filters", [])
    ):
        for item in walk_filter_nodes(node):
            yield f"filters[{index}]", item

    for index, node in enumerate(
        plan.get("having", [])
    ):
        for item in walk_filter_nodes(node):
            yield f"having[{index}]", item


def walk_logic_nodes(node):
    if not isinstance(node, dict) or "logic" not in node:
        return

    yield node
    for child in node.get("conditions", []):
        yield from walk_logic_nodes(child)


def referenced_metrics(plan):
    result = set(plan.get("metrics", []))
    result.update(
        item.get("field")
        for item in plan.get("order_by", [])
        if item.get("field")
    )
    for _, item in walk_all_filters(plan):
        if item.get("type") == "metric":
            result.add(item.get("target"))
    return {item for item in result if item}


def referenced_dimensions(plan):
    result = set(plan.get("dimensions", []))
    result.update(plan.get("group_by", []))
    for _, item in walk_all_filters(plan):
        if item.get("type") == "dimension":
            result.add(item.get("target"))
    return {item for item in result if item}


def infer_requested_capabilities(plan):
    requested = set()

    for _, item in walk_all_filters(plan):
        filter_type = item.get("type")
        feature = {
            "dimension": "dimension_filter",
            "metric": "metric_filter",
            "concept": "concept_filter",
            "entity": "entity_filter",
        }.get(filter_type)
        if feature:
            requested.add(feature)

    if plan.get("time_range") is not None:
        requested.add("time_filter")
    if plan.get("group_by"):
        requested.add("time_grouping" if plan.get("intent") == "trend_analysis" else "group_by")

    for root_name in ("filters", "having"):
        for node in plan.get(root_name, []):
            for logic_node in walk_logic_nodes(node):
                requested.add(f"{logic_node.get('logic')}_condition")

    intent = plan.get("intent")
    metrics = plan.get("metrics", [])
    if intent == "metric_query":
        requested.add("single_metric" if len(metrics) <= 1 else "multiple_metrics")
    elif intent in {"group_analysis", "trend_analysis"} and metrics:
        requested.add("metric_aggregation")
    elif intent == "ranking" and metrics:
        requested.add("metric_ranking")
    elif intent == "segment_analysis" and any(
        item.get("type") == "concept" for _, item in walk_all_filters(plan)
    ):
        requested.add("segment_filter")

    if intent == "trend_analysis" and plan.get("group_by"):
        requested.add("time_grouping")

    return requested


def metric_source_tables(metric_id, metrics_data, seen=None):
    seen = set() if seen is None else set(seen)
    if metric_id in seen:
        return set()
    seen.add(metric_id)

    metric = metrics_data.get("metrics", {}).get(metric_id, {})
    tables = set(metric.get("source_tables", []))
    for dependency in metric.get("derived_from", []):
        tables.update(metric_source_tables(dependency, metrics_data, seen))
    return tables


def compatible_metric_dimension(metric_id, dimension_id, metrics_data, dimensions_data, joins_data):
    metric = metrics_data.get("metrics", {}).get(metric_id, {})
    dimension = dimensions_data.get("dimensions", {}).get(dimension_id, {})

    if not metric or not dimension:
        return True

    grain = set(metric.get("grain", []))
    if dimension_id in grain:
        return True

    dimension_type = dimension.get("type")
    if dimension_type in {"time", "derived_time"}:
        return bool(grain.intersection({"date", "period"}))

    metric_tables = metric_source_tables(metric_id, metrics_data)
    dimension_table = dimension.get("source_table")
    dimension_source_tables = {
        str(item).split(".", 1)[0]
        for item in dimension.get("source_fields", [])
        if isinstance(item, str) and "." in item
    }

    if dimension_source_tables:
        return bool(metric_tables.intersection(dimension_source_tables))

    if dimension_table in metric_tables:
        return True

    for path_meta in joins_data.get("preferred_join_paths", {}).values():
        path_tables = set(path_meta.get("path", []))
        if dimension_table in path_tables and metric_tables.intersection(path_tables):
            return True

    if not dimension_table:
        return False

    graph = {}
    fact_tables = {
        "dws_cust_aset_d", "dws_cust_fin_d", "dwd_cust_tran_d", "dwd_cust_hold_d"
    }
    allowed = metric_tables | {dimension_table, "ads_cust_info_d", "dim_branch", "dim_product"}
    for join in joins_data.get("joins", {}).values():
        if not join.get("verified"):
            continue
        left = join.get("left_table")
        right = join.get("right_table")
        if left not in allowed or right not in allowed:
            continue
        if left in fact_tables - metric_tables or right in fact_tables - metric_tables:
            continue
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)

    frontier = list(metric_tables)
    visited = set(frontier)
    while frontier:
        current = frontier.pop()
        if current == dimension_table:
            return True
        for neighbor in graph.get(current, set()) - visited:
            visited.add(neighbor)
            frontier.append(neighbor)

    return False


def metric_requires_time(metric_id, metrics_data, metric_constraints_data):
    metric = metrics_data.get("metrics", {}).get(metric_id, {})
    local_constraints = metric.get("constraints", {})
    external_constraints = metric_constraints_data.get("constraints", {}).get(metric_id, {})
    return bool(
        local_constraints.get("required_time_range")
        or external_constraints.get("required_time_range")
    )


def validate_time_range_semantics(time_range, path="time_range"):
    errors = []
    if not isinstance(time_range, dict):
        return errors

    time_type = time_range.get("type")
    if time_type == "date_range":
        try:
            start = date.fromisoformat(time_range["start"])
            end = date.fromisoformat(time_range["end"])
            if start > end:
                errors.append(make_error(
                    "INVALID_TIME_RANGE", path, time_range,
                    "日期区间的 start 不能晚于 end。",
                ))
        except (KeyError, TypeError, ValueError):
            pass

    if time_type in {"start_of_period", "end_of_period"}:
        errors.extend(validate_time_range_semantics(time_range.get("period"), f"{path}.period"))

    return errors


# ============================================================
# Semantic Validation
# ============================================================

def validate_semantics(
    plan,
    intent_ids,
    metric_ids,
    dimension_ids,
    concept_ids,
    operator_ids,
    capability_ids,
    time_types,
    capability_data,
    confidence_data,
    metrics_data,
    dimensions_data,
    metric_constraints_data,
    entity_data,
    joins_data,
    operator_data,
    value_mappings_data=None,
):
    errors = []
    warnings = []
    policy = confidence_data.get("confidence_policy", {})
    execute_threshold = float(policy.get("execute_threshold", 0.85))
    clarification_threshold = float(policy.get("clarification_threshold", 0.60))

    # --------------------------------------------------------
    # 1. Intent
    # --------------------------------------------------------

    intent = plan.get("intent")

    if intent not in intent_ids:
        errors.append(
            make_error(
                "UNKNOWN_INTENT",
                "intent",
                intent,
                "Query Plan 使用了未注册 Intent。",
            )
        )

    # --------------------------------------------------------
    # 2. Capability
    # --------------------------------------------------------

    if (
        intent in intent_ids
        and intent not in capability_ids
    ):
        errors.append(
            make_error(
                "UNSUPPORTED_CAPABILITY",
                "intent",
                intent,
                "该 Intent 已注册，但没有对应 Capability 定义。",
            )
        )

    capability = capability_data.get("capabilities", {}).get(intent, {})
    allowed_subjects = set(capability.get("subject", []))
    subject = plan.get("subject")
    if allowed_subjects and subject not in allowed_subjects:
        errors.append(make_error(
            "UNSUPPORTED_COMBINATION", "subject", subject,
            f"Intent {intent} 不支持 subject={subject}。",
        ))

    global_features = {"and_condition", "or_condition", "not_condition", "ordering", "limit"}
    supported_features = set(capability.get("supported", [])) | global_features
    for feature in sorted(infer_requested_capabilities(plan) - supported_features):
        errors.append(make_error(
            "UNSUPPORTED_CAPABILITY", "intent", feature,
            f"Intent {intent} 不支持能力 {feature}。",
        ))

    # --------------------------------------------------------
    # 3. Metrics
    # --------------------------------------------------------

    for i, metric in enumerate(
        plan.get("metrics", [])
    ):
        if metric not in metric_ids:
            errors.append(
                make_error(
                    "UNKNOWN_METRIC",
                    f"metrics[{i}]",
                    metric,
                    "Metric 不存在于 Stage 2 Metric System。",
                )
            )

    # --------------------------------------------------------
    # 4. Dimensions
    # --------------------------------------------------------

    for i, dimension in enumerate(
        plan.get("dimensions", [])
    ):
        if dimension not in dimension_ids:
            errors.append(
                make_error(
                    "UNKNOWN_DIMENSION",
                    f"dimensions[{i}]",
                    dimension,
                    "Dimension 不存在于 dimensions.yaml。",
                )
            )

    for metric in sorted(referenced_metrics(plan) & metric_ids):
        for dimension in sorted(referenced_dimensions(plan) & dimension_ids):
            if not compatible_metric_dimension(
                metric, dimension, metrics_data, dimensions_data, joins_data
            ):
                errors.append(make_error(
                    "UNSUPPORTED_COMBINATION",
                    "metrics/dimensions",
                    {"metric": metric, "dimension": dimension},
                    "Metric 与 Dimension 缺少已验证的直接或首选 Join 路径。",
                ))

    for i, dimension in enumerate(
        plan.get("group_by", [])
    ):
        if dimension not in dimension_ids:
            errors.append(
                make_error(
                    "UNKNOWN_DIMENSION",
                    f"group_by[{i}]",
                    dimension,
                    "group_by 使用了未注册 Dimension。",
                )
            )

    # --------------------------------------------------------
    # 5. Order By
    # --------------------------------------------------------

    valid_order_fields = (
        metric_ids
        | dimension_ids
    )

    for i, item in enumerate(
        plan.get("order_by", [])
    ):
        field = item.get("field")

        if field not in valid_order_fields:
            errors.append(
                make_error(
                    "UNKNOWN_ORDER_FIELD",
                    f"order_by[{i}].field",
                    field,
                    "排序字段既不是已注册 Metric，也不是已注册 Dimension。",
                )
            )

    # --------------------------------------------------------
    # 6. Filters
    # --------------------------------------------------------

    for base_path, filter_item in walk_all_filters(plan):
        target = filter_item.get("target")
        filter_type = filter_item.get("type")
        operator = filter_item.get("operator")

        if operator not in operator_ids:
            errors.append(
                make_error(
                    "UNKNOWN_OPERATOR",
                    f"{base_path}.operator",
                    operator,
                    "Filter 使用了未注册 Operator。",
                )
            )

        if filter_type == "metric":
            if target not in metric_ids:
                errors.append(
                    make_error(
                        "UNKNOWN_METRIC",
                        f"{base_path}.target",
                        target,
                        "Metric Filter 引用了不存在的指标。",
                    )
                )

        elif filter_type == "dimension":
            if target not in dimension_ids:
                errors.append(
                    make_error(
                        "UNKNOWN_DIMENSION",
                        f"{base_path}.target",
                        target,
                        "Dimension Filter 引用了不存在的维度。",
                    )
                )
            else:
                mapping = (value_mappings_data or {}).get("mappings", {}).get(target, {})
                registered_values = mapping.get("values", {}) or {}
                dimension = dimensions_data.get("dimensions", {}).get(target, {})
                preferred_field = (mapping.get("filtering_rule") or {}).get("preferred_field")
                if (
                    registered_values
                    and preferred_field
                    and preferred_field == mapping.get("source_field") == dimension.get("source_field")
                ):
                    canonical_values = {str(item) for item in registered_values}
                    if str(mapping.get("source_field", "")).endswith("_name"):
                        # Query Plans may carry the stable semantic key (for
                        # example ``stock``) or an already-normalized storage
                        # label (``股票``).  The SQL compiler maps both through
                        # the same registered value contract.
                        canonical_values.update(str(item) for item in registered_values.values())
                    supplied = filter_item.get("value")
                    supplied_values = supplied if isinstance(supplied, list) else [supplied]
                    invalid = [item for item in supplied_values if str(item) not in canonical_values]
                    if invalid:
                        errors.append(make_error(
                            "INVALID_DIMENSION_VALUE", f"{base_path}.value", supplied,
                            "Dimension Filter 使用了未在 Value Mapping 中注册的 canonical value。",
                        ))

        elif filter_type == "concept":
            if target not in concept_ids:
                errors.append(
                    make_error(
                        "UNKNOWN_CONCEPT",
                        f"{base_path}.target",
                        target,
                        "Concept Filter 引用了未注册业务概念。",
                    )
                )

        elif filter_type == "entity":
            relation_to_type = {
                "held_product": "product",
                "traded_product": "product",
                "branch": "branch",
                "parent_branch": "parent_branch",
                "customer": "customer",
                "product_category": "product_category",
            }
            expected_type = relation_to_type.get(target)
            registered_types = set(entity_data.get("entities", {}))
            if expected_type not in registered_types:
                errors.append(make_error(
                    "INVALID_FILTER", f"{base_path}.target", target,
                    "Entity Filter 使用了未注册实体关系。",
                ))
            else:
                resolved_ids = {
                    str(entity.get("resolved", {}).get("id"))
                    for entity in plan.get("entities", [])
                    if entity.get("resolution_status") == "resolved"
                    and entity.get("entity_type") == expected_type
                    and isinstance(entity.get("resolved"), dict)
                }
                relation_only = (
                    filter_item.get("operator") in {"exists", "not_exists"}
                    and filter_item.get("value") is None
                )
                if not relation_only and str(filter_item.get("value")) not in resolved_ids:
                    errors.append(make_error(
                        "UNRESOLVED_ENTITY", base_path, filter_item.get("value"),
                        "Entity Filter 未引用 Plan 中已解析且类型匹配的实体。",
                    ))

        operator_meta = operator_data.get("operators", {}).get(operator, {})
        value_type = operator_meta.get("value_type")
        value = filter_item.get("value")
        invalid_value = (
            (value_type == "list" and (not isinstance(value, list) or not value))
            or (value_type == "range" and (not isinstance(value, list) or len(value) != 2))
            or (value_type == "scalar" and isinstance(value, (list, dict)))
            or (
                value_type == "none"
                and filter_type != "entity"
                and "value" in filter_item
                and value is not None
            )
        )
        if invalid_value:
            errors.append(make_error(
                "INVALID_FILTER", f"{base_path}.value", value,
                f"Operator {operator} 的值不符合 {value_type} 类型要求。",
            ))

        if plan.get("status") == "ready" and filter_item.get("confidence", 0) < execute_threshold:
            errors.append(make_error(
                "LOW_CONFIDENCE", f"{base_path}.confidence", filter_item.get("confidence"),
                f"Ready Plan 的筛选条件置信度必须达到 {execute_threshold:.2f}。",
            ))

    # --------------------------------------------------------
    # 7. Entity
    # --------------------------------------------------------

    for i, entity in enumerate(
        plan.get("entities", [])
    ):
        status = entity.get(
            "resolution_status"
        )

        if status == "ambiguous":
            errors.append(
                make_error(
                    "UNRESOLVED_ENTITY",
                    f"entities[{i}]",
                    entity.get("surface"),
                    "实体存在多个候选，必须先澄清。",
                )
            )

        elif status == "not_found":
            errors.append(
                make_error(
                    "UNRESOLVED_ENTITY",
                    f"entities[{i}]",
                    entity.get("surface"),
                    "数据库中未找到对应实体。",
                )
            )

        elif status != "resolved":
            errors.append(
                make_error(
                    "UNRESOLVED_ENTITY",
                    f"entities[{i}]",
                    entity.get("surface"),
                    "实体尚未完成解析。",
                )
            )
        elif plan.get("status") == "ready" and entity.get("confidence", 0) < execute_threshold:
            errors.append(make_error(
                "LOW_CONFIDENCE", f"entities[{i}].confidence", entity.get("confidence"),
                f"Ready Plan 的实体解析置信度必须达到 {execute_threshold:.2f}。",
            ))

    # --------------------------------------------------------
    # 8. Time
    # --------------------------------------------------------

    time_range = plan.get("time_range")

    if isinstance(time_range, dict):
        time_type = time_range.get("type")

        if time_type not in time_types:
            errors.append(
                make_error(
                    "INVALID_TIME_RANGE",
                    "time_range.type",
                    time_type,
                    "使用了未注册时间语义。",
                )
            )

        errors.extend(validate_time_range_semantics(time_range))

    has_time_clarification = any(
        item.get("type") == "time" for item in plan.get("ambiguities", [])
    )
    for metric in sorted(referenced_metrics(plan) & metric_ids):
        if (
            metric_requires_time(metric, metrics_data, metric_constraints_data)
            and time_range is None
            and not (plan.get("status") == "needs_clarification" and has_time_clarification)
        ):
            errors.append(make_error(
                "MISSING_REQUIRED_TIME_RANGE", "time_range", metric,
                f"Metric {metric} 的口径要求明确时间范围。",
            ))

    requirements = capability.get("requires", {})
    if requirements.get("time_range") and time_range is None:
        errors.append(make_error(
            "MISSING_REQUIRED_TIME_RANGE", "time_range", intent,
            f"Intent {intent} 要求明确时间范围。",
        ))
    if requirements.get("resolved_customer"):
        has_customer = any(
            entity.get("entity_type") == "customer"
            and entity.get("resolution_status") == "resolved"
            for entity in plan.get("entities", [])
        )
        if not has_customer:
            errors.append(make_error(
                "UNRESOLVED_ENTITY", "entities", "customer",
                "客户画像必须包含唯一解析的客户实体。",
            ))
    if requirements.get("comparison_targets"):
        values = {
            json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True)
            for _, item in walk_all_filters(plan)
            if "value" in item
        }
        if len(values) < 2 and plan.get("context", {}).get("operation") != "compare":
            errors.append(make_error(
                "UNSUPPORTED_COMBINATION", "filters", None,
                "对比分析至少需要两个明确对比目标或 compare 上下文。",
            ))

    # --------------------------------------------------------
    # 9. Clarification consistency
    # --------------------------------------------------------

    status = plan.get("status")
    ambiguities = plan.get(
        "ambiguities",
        []
    )

    if (
        status == "needs_clarification"
        and not ambiguities
    ):
        errors.append(
            make_error(
                "MISSING_AMBIGUITY",
                "ambiguities",
                message=(
                    "status=needs_clarification 时，"
                    "必须至少记录一个歧义。"
                ),
            )
        )

    if (
        status == "ready"
        and ambiguities
    ):
        errors.append(
            make_error(
                "UNRESOLVED_AMBIGUITY",
                "ambiguities",
                message=(
                    "Plan 标记为 ready，"
                    "但仍存在未解决歧义。"
                ),
            )
        )

    # --------------------------------------------------------
    # 10. Assumptions
    # --------------------------------------------------------

    assumptions = plan.get(
        "assumptions",
        []
    )

    undeclared_assumptions = [
        item for item in assumptions
        if not item.get("source") or item.get("review_required") is True
    ]
    business_default_filters = [
        item for _, item in walk_all_filters(plan)
        if item.get("source") == "business_default"
    ]
    if undeclared_assumptions or (business_default_filters and not assumptions):
        errors.append(make_error(
            "UNDECLARED_ASSUMPTION", "assumptions",
            message="业务默认或待审查假设必须声明来源并在执行前完成审查。",
        ))
    elif assumptions:
        warnings.append(make_warning(
            "ASSUMPTION_AUDIT", "assumptions",
            message="Plan 含有已声明假设，执行日志必须保留其来源。",
        ))

    # --------------------------------------------------------
    # 11. Confidence
    # --------------------------------------------------------

    confidence = plan.get(
        "confidence",
        {}
    )

    overall = confidence.get("overall")
    if overall is not None:

        # ready 状态代表准备执行，
        # 因此置信度必须足够高
        if status == "ready":

            if overall < execute_threshold:
                errors.append(
                    make_error(
                        "LOW_CONFIDENCE",
                        "confidence.overall",
                        overall,
                        (
                            "Plan 标记为 ready，"
                            f"但整体置信度低于执行阈值 {execute_threshold:.2f}。"
                        ),
                    )
                )

        # needs_clarification 本身就是合法的低置信度状态
        elif status == "needs_clarification":

            if overall >= execute_threshold:
                warnings.append(
                    make_warning(
                        "CLARIFICATION_HIGH_CONFIDENCE",
                        "confidence.overall",
                        overall,
                        (
                            "Plan 需要澄清，但整体置信度较高；"
                            "建议检查是否确实存在未解决歧义。"
                        ),
                    )
                )

        elif status == "invalid":
            pass

    if overall is None:
        errors.append(make_error(
            "LOW_CONFIDENCE", "confidence.overall",
            message="缺少整体置信度，Fail Closed。",
        ))

    if status == "ready":
        for component in policy.get("critical_components", []):
            score = confidence.get(component)
            if score is None:
                errors.append(make_error(
                    "LOW_CONFIDENCE", f"confidence.{component}",
                    message=f"Ready Plan 缺少关键组件 {component} 的置信度。",
                ))
            elif score < clarification_threshold:
                errors.append(make_error(
                    "LOW_CONFIDENCE", f"confidence.{component}", score,
                    f"关键组件 {component} 的置信度低于澄清阈值 {clarification_threshold:.2f}。",
                ))

    return errors, warnings


# ============================================================
# 单个 Plan 校验
# ============================================================

def load_registries():
    intent_data = load_yaml(FILES["intents"])
    operator_data = load_yaml(FILES["operators"])
    time_data = load_yaml(FILES["time_semantics"])
    capability_data = load_yaml(FILES["capabilities"])
    confidence_data = load_yaml(FILES["confidence"])
    metrics_data = load_yaml(FILES["metrics"])
    metric_constraints_data = load_yaml(FILES["metric_constraints"])
    dimensions_data = load_yaml(FILES["dimensions"])
    dictionary_data = load_yaml(FILES["dictionary"])
    entity_data = load_yaml(FILES["entities"])
    joins_data = load_yaml(FILES["joins"])
    value_mappings_data = load_yaml(FILES["value_mappings"])

    return {
        "intent_ids": extract_intent_ids(intent_data),
        "metric_ids": extract_metric_ids(metrics_data),
        "dimension_ids": extract_dimension_ids(dimensions_data),
        "concept_ids": extract_concept_ids(dictionary_data),
        "operator_ids": extract_operator_ids(operator_data),
        "capability_ids": extract_capability_ids(capability_data),
        "time_types": extract_time_types(time_data),
        "capability_data": capability_data,
        "confidence_data": confidence_data,
        "metrics_data": metrics_data,
        "dimensions_data": dimensions_data,
        "metric_constraints_data": metric_constraints_data,
        "entity_data": entity_data,
        "joins_data": joins_data,
        "operator_data": operator_data,
        "value_mappings_data": value_mappings_data,
    }


def validate_plan_data(plan, registries=None, source="<memory>"):
    registries = registries or load_registries()

    structural_errors = validate_structure(plan, FILES["schema"])
    if structural_errors:
        return {
            "file": source,
            "valid": False,
            "errors": structural_errors,
            "warnings": [],
        }

    try:
        QueryPlan.model_validate(plan)
    except ValidationError as exc:
        return {
            "file": source,
            "valid": False,
            "errors": [
                make_error(
                    "STRUCTURAL_ERROR",
                    ".".join(str(item) for item in error.get("loc", ())) or "$",
                    message=error.get("msg"),
                )
                for error in exc.errors()
            ],
            "warnings": [],
        }

    semantic_errors, warnings = validate_semantics(plan=plan, **registries)
    return {
        "file": source,
        "valid": len(semantic_errors) == 0,
        "errors": semantic_errors,
        "warnings": warnings,
    }


def validate_plan(
    plan_path: Path,
    registries,
):
    try:
        plan = load_json(plan_path)

    except Exception as e:
        return {
            "file": str(plan_path),
            "valid": False,
            "errors": [
                make_error(
                    "INVALID_JSON",
                    "$",
                    message=str(e),
                )
            ],
            "warnings": [],
        }

    return validate_plan_data(plan, registries, source=str(plan_path))


# ============================================================
# 主程序
# ============================================================

def main():
    print("=" * 78)
    print(
        "Stage 4 Generic Query Plan Validator"
    )
    print("=" * 78)

    try:
        registries = load_registries()

    except Exception as e:
        print(
            f"❌ Metadata 加载失败: {e}"
        )
        sys.exit(1)

    print(
        f"Intent Registry: "
        f"{len(registries['intent_ids'])}"
    )

    print(
        f"Metric Registry: "
        f"{len(registries['metric_ids'])}"
    )

    print(
        f"Dimension Registry: "
        f"{len(registries['dimension_ids'])}"
    )

    print(
        f"Business Concept Registry: "
        f"{len(registries['concept_ids'])}"
    )

    print(
        f"Operator Registry: "
        f"{len(registries['operator_ids'])}"
    )

    print(
        f"Capability Registry: "
        f"{len(registries['capability_ids'])}"
    )

    print(
        f"Time Semantics: "
        f"{len(registries['time_types'])}"
    )

    print("=" * 78)

    # --------------------------------------------------------
    # 可指定 Plan 文件
    # --------------------------------------------------------

    if len(sys.argv) > 1:
        plan_paths = [
            Path(arg).resolve()
            for arg in sys.argv[1:]
        ]

    else:
        plan_paths = sorted(
            EXAMPLE_DIR.glob("*.json")
        )

    if not plan_paths:
        print(
            "❌ 没有找到 Query Plan JSON 文件"
        )
        sys.exit(1)

    all_valid = True

    for plan_path in plan_paths:
        print()
        print("-" * 78)
        print(
            f"检查 Plan: "
            f"{plan_path.name}"
        )

        result = validate_plan(
            plan_path,
            registries,
        )

        if result["warnings"]:
            print(
                f"⚠ 警告 "
                f"{len(result['warnings'])} 条"
            )

            for warning in result[
                "warnings"
            ]:
                print(
                    f"  [{warning['code']}] "
                    f"{warning['path']}: "
                    f"{warning.get('message', '')}"
                )

        if result["errors"]:
            all_valid = False

            print(
                f"❌ 错误 "
                f"{len(result['errors'])} 条"
            )

            for error in result[
                "errors"
            ]:
                print(
                    f"  [{error['code']}] "
                    f"{error['path']}: "
                    f"{error.get('message', '')}"
                )

        else:
            print(
                "✅ Structural Validation 通过"
            )

            print(
                "✅ Semantic Validation 通过"
            )

    print()
    print("=" * 78)

    if all_valid:
        print(
            "✅ 所有 Query Plan 校验通过"
        )

    else:
        print(
            "❌ 至少一个 Query Plan 校验失败"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
