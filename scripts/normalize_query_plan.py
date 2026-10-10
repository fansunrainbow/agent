from pathlib import Path
import json
import sys

import yaml


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]

METADATA_DIR = ROOT / "metadata"


FILES = {
    "operators": METADATA_DIR / "operator_registry.yaml",
    "time_semantics": METADATA_DIR / "time_semantics.yaml",
    "concept_aliases": METADATA_DIR / "concept_aliases.yaml",
    "metric_aliases": METADATA_DIR / "metric_aliases.yaml",
}


# ============================================================
# 基础读取
# ============================================================

def load_yaml(path: Path):
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# Alias Map
# ============================================================

def build_operator_alias_map(operator_data):
    result = {}

    operators = operator_data.get("operators", {})

    for operator_id, meta in operators.items():

        # canonical 本身
        result[str(operator_id).strip().lower()] = operator_id

        # SQL 形式
        sql = meta.get("sql")
        if sql:
            result[str(sql).strip().lower()] = operator_id

        # 中文/自然语言 alias
        for alias in meta.get("aliases", []):
            result[str(alias).strip().lower()] = operator_id

    return result


def build_concept_alias_map(alias_data):
    result = {}

    aliases = alias_data.get("aliases", {})

    for concept_id, values in aliases.items():

        result[str(concept_id).strip().lower()] = concept_id

        for alias in values or []:
            result[str(alias).strip().lower()] = concept_id

    return result


def build_metric_alias_map(alias_data):
    result = {}

    aliases = alias_data.get("aliases", {})

    for metric_id, values in aliases.items():

        result[str(metric_id).strip().lower()] = metric_id

        # 兼容 list
        if isinstance(values, list):
            for alias in values:
                result[str(alias).strip().lower()] = metric_id

        # 兼容 dict
        elif isinstance(values, dict):
            for alias in values.get("aliases", []):
                result[str(alias).strip().lower()] = metric_id

    return result


# ============================================================
# 基础 Canonical Normalization
# ============================================================

CITY_NORMALIZATION = {
    "南京市": "南京",
    "南京": "南京",
    "nanjing": "南京",

    "苏州市": "苏州",
    "苏州": "苏州",
    "suzhou": "苏州",

    "上海市": "上海",
    "上海": "上海",
    "shanghai": "上海",

    "北京市": "北京",
    "北京": "北京",
    "beijing": "北京",
}


def normalize_city(value):
    if not isinstance(value, str):
        return value

    key = value.strip()

    lowered = key.lower()

    if lowered in CITY_NORMALIZATION:
        return CITY_NORMALIZATION[lowered]

    if key in CITY_NORMALIZATION:
        return CITY_NORMALIZATION[key]

    # 通用规则：中文城市名末尾“市”
    if key.endswith("市") and len(key) > 1:
        return key[:-1]

    return key


def normalize_scalar(value):
    if isinstance(value, str):
        return value.strip()

    return value


# ============================================================
# Operator Normalization
# ============================================================

def normalize_operator(operator, alias_map):
    if not isinstance(operator, str):
        return operator

    key = operator.strip().lower()

    return alias_map.get(key, operator)


# ============================================================
# Metric / Concept Normalization
# ============================================================

def normalize_metric(metric, metric_alias_map):
    if not isinstance(metric, str):
        return metric

    key = metric.strip().lower()

    return metric_alias_map.get(key, metric)


def normalize_concept(concept, concept_alias_map):
    if not isinstance(concept, str):
        return concept

    key = concept.strip().lower()

    return concept_alias_map.get(key, concept)


# ============================================================
# Time Normalization
# ============================================================

def normalize_time_range(time_range):
    if not isinstance(time_range, dict):
        return time_range

    result = dict(time_range)

    time_type = result.get("type")

    if isinstance(time_type, str):
        result["type"] = time_type.strip().lower()

    # quarter
    if result.get("type") == "quarter":

        quarter = result.get("quarter")

        if isinstance(quarter, str):
            q = quarter.strip().lower()

            mapping = {
                "q1": 1,
                "q2": 2,
                "q3": 3,
                "q4": 4,
                "第一季度": 1,
                "第二季度": 2,
                "第三季度": 3,
                "第四季度": 4,
            }

            if q in mapping:
                result["quarter"] = mapping[q]

            elif q.isdigit():
                result["quarter"] = int(q)

    # month
    if result.get("type") == "month":

        month = result.get("month")

        if isinstance(month, str) and month.strip().isdigit():
            result["month"] = int(month.strip())

    # last_n_days / last_n_months
    if result.get("type") in {
        "last_n_days",
        "last_n_months",
    }:

        n = result.get("n")

        if isinstance(n, str) and n.strip().isdigit():
            result["n"] = int(n.strip())

    # 嵌套 period
    if "period" in result:
        result["period"] = normalize_time_range(
            result["period"]
        )

    return result


# ============================================================
# Filter Normalization
# ============================================================

def normalize_filter_node(
    node,
    operator_alias_map,
    metric_alias_map,
    concept_alias_map,
):
    if not isinstance(node, dict):
        return node

    result = dict(node)

    # 逻辑树
    if "logic" in result:

        logic = result.get("logic")

        if isinstance(logic, str):
            logic_map = {
                "and": "and",
                "且": "and",
                "并且": "and",
                "同时": "and",

                "or": "or",
                "或": "or",
                "或者": "or",

                "not": "not",
                "非": "not",
                "不": "not",
            }

            result["logic"] = logic_map.get(
                logic.strip().lower(),
                logic.strip().lower(),
            )

        result["conditions"] = [
            normalize_filter_node(
                child,
                operator_alias_map,
                metric_alias_map,
                concept_alias_map,
            )
            for child in result.get("conditions", [])
        ]

        return result

    # 简单 Filter
    operator = result.get("operator")

    if operator is not None:
        result["operator"] = normalize_operator(
            operator,
            operator_alias_map,
        )

    filter_type = result.get("type")
    target = result.get("target")

    if filter_type == "metric":
        result["target"] = normalize_metric(
            target,
            metric_alias_map,
        )

    elif filter_type == "concept":
        result["target"] = normalize_concept(
            target,
            concept_alias_map,
        )

    elif filter_type == "dimension":
        if target == "city" and "value" in result:
            result["value"] = normalize_city(
                result["value"]
            )

    if "value" in result:
        result["value"] = normalize_scalar(
            result["value"]
        )

    return result


# ============================================================
# Entity Normalization
# ============================================================

def normalize_entity(entity):
    if not isinstance(entity, dict):
        return entity

    result = dict(entity)

    if isinstance(result.get("surface"), str):
        result["surface"] = (
            result["surface"].strip()
        )

    resolved = result.get("resolved")

    if isinstance(resolved, dict):
        resolved = dict(resolved)

        if isinstance(resolved.get("name"), str):
            resolved["name"] = (
                resolved["name"].strip()
            )

        result["resolved"] = resolved

    return result


# ============================================================
# 整体 Query Plan Normalization
# ============================================================

def normalize_query_plan(plan):
    operator_data = load_yaml(
        FILES["operators"]
    )

    concept_alias_data = load_yaml(
        FILES["concept_aliases"]
    )

    metric_alias_data = load_yaml(
        FILES["metric_aliases"]
    )

    operator_alias_map = build_operator_alias_map(
        operator_data
    )

    concept_alias_map = build_concept_alias_map(
        concept_alias_data
    )

    metric_alias_map = build_metric_alias_map(
        metric_alias_data
    )

    result = dict(plan)

    # --------------------------------------------------------
    # Intent / Subject / Status
    # --------------------------------------------------------

    for field in (
        "status",
        "intent",
        "subject",
    ):
        value = result.get(field)

        if isinstance(value, str):
            result[field] = (
                value.strip().lower()
            )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    result["metrics"] = [
        normalize_metric(
            metric,
            metric_alias_map,
        )
        for metric in result.get("metrics", [])
    ]

    # --------------------------------------------------------
    # Dimensions
    # --------------------------------------------------------

    result["dimensions"] = [
        str(dimension).strip()
        for dimension in result.get(
            "dimensions",
            []
        )
    ]

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------

    result["filters"] = [
        normalize_filter_node(
            node,
            operator_alias_map,
            metric_alias_map,
            concept_alias_map,
        )
        for node in result.get("filters", [])
    ]

    result["having"] = [
        normalize_filter_node(
            node,
            operator_alias_map,
            metric_alias_map,
            concept_alias_map,
        )
        for node in result.get("having", [])
    ]

    # --------------------------------------------------------
    # Entities
    # --------------------------------------------------------

    result["entities"] = [
        normalize_entity(entity)
        for entity in result.get(
            "entities",
            []
        )
    ]

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    result["time_range"] = (
        normalize_time_range(
            result.get("time_range")
        )
    )

    # --------------------------------------------------------
    # Group By
    # --------------------------------------------------------

    result["group_by"] = [
        str(item).strip()
        for item in result.get(
            "group_by",
            []
        )
    ]

    # --------------------------------------------------------
    # Order By
    # --------------------------------------------------------

    normalized_order_by = []

    for item in result.get(
        "order_by",
        []
    ):
        item = dict(item)

        field = item.get("field")

        if isinstance(field, str):
            canonical_metric = normalize_metric(
                field,
                metric_alias_map,
            )

            item["field"] = canonical_metric

        direction = item.get("direction")

        if isinstance(direction, str):
            direction_map = {
                "asc": "asc",
                "ascending": "asc",
                "升序": "asc",
                "从低到高": "asc",

                "desc": "desc",
                "descending": "desc",
                "降序": "desc",
                "从高到低": "desc",
            }

            item["direction"] = (
                direction_map.get(
                    direction.strip().lower(),
                    direction.strip().lower(),
                )
            )

        normalized_order_by.append(item)

    result["order_by"] = normalized_order_by

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output = result.get("output")

    if isinstance(output, dict):
        output = dict(output)

        for field in ("mode", "format"):
            if isinstance(output.get(field), str):
                output[field] = (
                    output[field]
                    .strip()
                    .lower()
                )

        result["output"] = output

    return result


# ============================================================
# 主程序
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(
            "用法："
            "python scripts/normalize_query_plan.py "
            "<query_plan.json> "
            "[output.json]"
        )
        sys.exit(1)

    input_path = Path(
        sys.argv[1]
    ).resolve()

    if not input_path.exists():
        print(
            f"❌ 输入文件不存在: "
            f"{input_path}"
        )
        sys.exit(1)

    try:
        plan = load_json(input_path)

    except Exception as e:
        print(
            f"❌ JSON 加载失败: {e}"
        )
        sys.exit(1)

    normalized = normalize_query_plan(plan)

    print("=" * 78)
    print("Query Plan Normalizer")
    print("=" * 78)

    print(
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
        )
    )

    if len(sys.argv) >= 3:

        output_path = Path(
            sys.argv[2]
        ).resolve()

        save_json(
            output_path,
            normalized,
        )

        print()
        print(
            f"✅ 已保存归一化结果: "
            f"{output_path}"
        )


if __name__ == "__main__":
    main()
