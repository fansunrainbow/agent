from pathlib import Path
import json
from collections import Counter, defaultdict
import sys

import yaml


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]

TEST_DIR = ROOT / "tests" / "query_plan"
METADATA_DIR = ROOT / "metadata"


FILES = {
    "intents": METADATA_DIR / "intent_registry.yaml",
    "metrics": METADATA_DIR / "metrics.yaml",
    "dimensions": METADATA_DIR / "dimensions.yaml",
}


# ============================================================
# 基础读取
# ============================================================

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
                            result.add(
                                str(item[candidate])
                            )
                            break

            return result

    return set()


def extract_intent_ids(data):
    return extract_keys(
        data,
        ["intents"]
    )


def extract_metric_ids(data):
    return extract_keys(
        data,
        ["metrics"]
    )


def extract_dimension_ids(data):
    return extract_keys(
        data,
        ["dimensions"]
    )


# ============================================================
# Filter 遍历
# ============================================================

def walk_filter_nodes(node):
    if not isinstance(node, dict):
        return

    if "logic" in node:
        for child in node.get(
            "conditions",
            []
        ):
            yield from walk_filter_nodes(child)

    else:
        yield node


def walk_plan_filters(plan):
    for node in plan.get(
        "filters",
        []
    ):
        yield from walk_filter_nodes(node)

    for node in plan.get(
        "having",
        []
    ):
        yield from walk_filter_nodes(node)


# ============================================================
# Coverage
# ============================================================

def percentage(part, total):
    if total == 0:
        return 0.0

    return part / total * 100


def main():
    print("=" * 80)
    print("Stage 4 Query Plan Coverage Inspector")
    print("=" * 80)

    if not TEST_DIR.exists():
        print(
            f"❌ 测试目录不存在: {TEST_DIR}"
        )
        return

    test_files = sorted(
        TEST_DIR.glob("*.json")
    )

    if not test_files:
        print(
            "❌ tests/query_plan/ 中没有测试 JSON"
        )
        return

    # --------------------------------------------------------
    # 加载 Registry
    # --------------------------------------------------------

    intent_registry = extract_intent_ids(
        load_yaml(FILES["intents"])
    )

    metric_registry = extract_metric_ids(
        load_yaml(FILES["metrics"])
    )

    dimension_registry = extract_dimension_ids(
        load_yaml(FILES["dimensions"])
    )

    # --------------------------------------------------------
    # Coverage 数据
    # --------------------------------------------------------

    category_counter = Counter()
    status_counter = Counter()
    intent_counter = Counter()

    used_metrics = Counter()
    used_dimensions = Counter()
    used_concepts = Counter()
    used_entity_types = Counter()
    used_operators = Counter()
    used_time_types = Counter()
    used_logic = Counter()
    used_context_operations = Counter()

    expected_error_codes = Counter()

    total_cases = 0

    # --------------------------------------------------------
    # 遍历测试
    # --------------------------------------------------------

    for path in test_files:
        try:
            case_data = load_json(path)

        except Exception as e:
            print(
                f"⚠ 跳过 {path.name}: {e}"
            )
            continue

        total_cases += 1

        category = case_data.get(
            "category",
            "unknown"
        )

        category_counter[
            category
        ] += 1

        expected = case_data.get(
            "expected",
            {}
        )

        for code in expected.get(
            "error_codes",
            []
        ):
            expected_error_codes[
                code
            ] += 1

        plan = case_data.get(
            "plan",
            {}
        )

        status = plan.get(
            "status"
        )

        if status:
            status_counter[
                status
            ] += 1

        intent = plan.get(
            "intent"
        )

        if intent:
            intent_counter[
                intent
            ] += 1

        # Metrics
        for metric in plan.get(
            "metrics",
            []
        ):
            used_metrics[
                metric
            ] += 1

        # Dimensions
        for dimension in plan.get(
            "dimensions",
            []
        ):
            used_dimensions[
                dimension
            ] += 1

        for dimension in plan.get(
            "group_by",
            []
        ):
            used_dimensions[
                dimension
            ] += 1

        # Filters
        for item in walk_plan_filters(
            plan
        ):
            filter_type = item.get(
                "type"
            )

            target = item.get(
                "target"
            )

            operator = item.get(
                "operator"
            )

            if operator:
                used_operators[
                    operator
                ] += 1

            if (
                filter_type == "metric"
                and target
            ):
                used_metrics[
                    target
                ] += 1

            elif (
                filter_type == "dimension"
                and target
            ):
                used_dimensions[
                    target
                ] += 1

            elif (
                filter_type == "concept"
                and target
            ):
                used_concepts[
                    target
                ] += 1

        # 逻辑树
        def inspect_logic(node):
            if not isinstance(
                node,
                dict
            ):
                return

            logic = node.get(
                "logic"
            )

            if logic:
                used_logic[
                    logic
                ] += 1

                for child in node.get(
                    "conditions",
                    []
                ):
                    inspect_logic(
                        child
                    )

        for node in plan.get(
            "filters",
            []
        ):
            inspect_logic(node)

        for node in plan.get(
            "having",
            []
        ):
            inspect_logic(node)

        # Entity
        for entity in plan.get(
            "entities",
            []
        ):
            entity_type = entity.get(
                "entity_type"
            )

            if entity_type:
                used_entity_types[
                    entity_type
                ] += 1

        # Time
        time_range = plan.get(
            "time_range"
        )

        if isinstance(
            time_range,
            dict
        ):
            time_type = time_range.get(
                "type"
            )

            if time_type:
                used_time_types[
                    time_type
                ] += 1

        # Context
        context = plan.get(
            "context",
            {}
        )

        operation = context.get(
            "operation"
        )

        if operation:
            used_context_operations[
                operation
            ] += 1

    # ========================================================
    # 输出统计
    # ========================================================

    print()
    print("一、测试总量")
    print("-" * 80)

    print(
        f"测试文件数量: {total_cases}"
    )

    print()
    print("类别分布:")

    for category, count in sorted(
        category_counter.items()
    ):
        print(
            f"  {category}: {count}"
        )

    # --------------------------------------------------------
    # Intent
    # --------------------------------------------------------

    covered_intents = (
        set(intent_counter.keys())
        & intent_registry
    )

    missing_intents = (
        intent_registry
        - covered_intents
    )

    print()
    print("二、Intent Coverage")
    print("-" * 80)

    print(
        f"注册 Intent: "
        f"{len(intent_registry)}"
    )

    print(
        f"已覆盖 Intent: "
        f"{len(covered_intents)}"
    )

    print(
        "Intent Coverage: "
        f"{percentage(len(covered_intents), len(intent_registry)):.2f}%"
    )

    print(
        "已覆盖:",
        sorted(covered_intents)
    )

    if missing_intents:
        print(
            "未覆盖:",
            sorted(missing_intents)
        )
    else:
        print(
            "✅ 所有注册 Intent 均有测试覆盖"
        )

    # --------------------------------------------------------
    # Metric
    # --------------------------------------------------------

    registered_used_metrics = (
        set(used_metrics.keys())
        & metric_registry
    )

    missing_metrics = (
        metric_registry
        - registered_used_metrics
    )

    print()
    print("三、Metric Coverage")
    print("-" * 80)

    print(
        f"注册 Metric: "
        f"{len(metric_registry)}"
    )

    print(
        f"已覆盖 Metric: "
        f"{len(registered_used_metrics)}"
    )

    print(
        "Metric Coverage: "
        f"{percentage(len(registered_used_metrics), len(metric_registry)):.2f}%"
    )

    if missing_metrics:
        print(
            "未覆盖 Metric:"
        )

        for metric in sorted(
            missing_metrics
        ):
            print(
                f"  - {metric}"
            )

    else:
        print(
            "✅ 所有 Metric 均有测试覆盖"
        )

    # --------------------------------------------------------
    # Dimension
    # --------------------------------------------------------

    registered_used_dimensions = (
        set(used_dimensions.keys())
        & dimension_registry
    )

    missing_dimensions = (
        dimension_registry
        - registered_used_dimensions
    )

    print()
    print("四、Dimension Coverage")
    print("-" * 80)

    print(
        f"注册 Dimension: "
        f"{len(dimension_registry)}"
    )

    print(
        f"已覆盖 Dimension: "
        f"{len(registered_used_dimensions)}"
    )

    print(
        "Dimension Coverage: "
        f"{percentage(len(registered_used_dimensions), len(dimension_registry)):.2f}%"
    )

    if missing_dimensions:
        print(
            "未覆盖 Dimension:"
        )

        for dimension in sorted(
            missing_dimensions
        ):
            print(
                f"  - {dimension}"
            )

    else:
        print(
            "✅ 所有 Dimension 均有测试覆盖"
        )

    # --------------------------------------------------------
    # 其他覆盖
    # --------------------------------------------------------

    print()
    print("五、Query Plan Feature Coverage")
    print("-" * 80)

    print(
        "Status:",
        dict(status_counter)
    )

    print(
        "Logic:",
        dict(used_logic)
    )

    print(
        "Operators:",
        dict(used_operators)
    )

    print(
        "Entity Types:",
        dict(used_entity_types)
    )

    print(
        "Time Types:",
        dict(used_time_types)
    )

    print(
        "Context Operations:",
        dict(used_context_operations)
    )

    print(
        "Business Concepts:",
        dict(used_concepts)
    )

    # --------------------------------------------------------
    # Hallucination Coverage
    # --------------------------------------------------------

    print()
    print("六、Hallucination / Invalid Coverage")
    print("-" * 80)

    if expected_error_codes:

        for code, count in sorted(
            expected_error_codes.items()
        ):
            print(
                f"  {code}: {count}"
            )

    else:
        print(
            "⚠ 没有发现 Invalid / Hallucination 错误码测试"
        )

    recommended_codes = {
        "UNKNOWN_METRIC",
        "UNKNOWN_DIMENSION",
        "UNKNOWN_CONCEPT",
        "UNRESOLVED_ENTITY",
        "LOW_CONFIDENCE",
        "STRUCTURAL_ERROR",
    }

    covered_codes = set(
        expected_error_codes.keys()
    )

    missing_codes = (
        recommended_codes
        - covered_codes
    )

    if missing_codes:
        print()
        print(
            "建议补充错误码覆盖:"
        )

        for code in sorted(
            missing_codes
        ):
            print(
                f"  - {code}"
            )

    else:
        print()
        print(
            "✅ 核心幻觉/非法 Plan 错误类型均已覆盖"
        )

    # --------------------------------------------------------
    # 总结
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("Coverage Summary")
    print("=" * 80)

    print(
        f"Tests: {total_cases}"
    )

    print(
        f"Intent Coverage: "
        f"{percentage(len(covered_intents), len(intent_registry)):.2f}%"
    )

    print(
        f"Metric Coverage: "
        f"{percentage(len(registered_used_metrics), len(metric_registry)):.2f}%"
    )

    print(
        f"Dimension Coverage: "
        f"{percentage(len(registered_used_dimensions), len(dimension_registry)):.2f}%"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()
