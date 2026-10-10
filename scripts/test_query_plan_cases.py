from pathlib import Path
import json
import sys

from validate_query_plan import (
    load_yaml,
    validate_plan,
    extract_intent_ids,
    extract_metric_ids,
    extract_dimension_ids,
    extract_concept_ids,
    extract_operator_ids,
    extract_capability_ids,
    extract_time_types,
    FILES,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests" / "query_plan"


def load_case(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_registries():
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

    return {
        "intent_ids": extract_intent_ids(intent_data),
        "metric_ids": extract_metric_ids(metrics_data),
        "dimension_ids": extract_dimension_ids(
            dimensions_data
        ),
        "concept_ids": extract_concept_ids(
            dictionary_data
        ),
        "operator_ids": extract_operator_ids(
            operator_data
        ),
        "capability_ids": extract_capability_ids(
            capability_data
        ),
        "time_types": extract_time_types(
            time_data
        ),
        "capability_data": capability_data,
        "confidence_data": confidence_data,
        "metrics_data": metrics_data,
        "dimensions_data": dimensions_data,
        "metric_constraints_data": metric_constraints_data,
        "entity_data": entity_data,
        "joins_data": joins_data,
        "operator_data": operator_data,
    }


def check_expected_result(case_data, validator_result):
    expected = case_data.get("expected", {})

    expected_valid = expected.get("valid")
    expected_error_codes = set(
        expected.get("error_codes", [])
    )

    actual_valid = validator_result["valid"]

    actual_error_codes = {
        item["code"]
        for item in validator_result["errors"]
    }

    problems = []

    if (
        expected_valid is not None
        and expected_valid != actual_valid
    ):
        problems.append(
            f"expected.valid={expected_valid}, "
            f"actual.valid={actual_valid}"
        )

    if expected_error_codes:
        missing = (
            expected_error_codes
            - actual_error_codes
        )

        if missing:
            problems.append(
                "缺少预期错误码: "
                + ", ".join(sorted(missing))
            )

    return problems


def main():
    print("=" * 78)
    print("Stage 4 Query Plan Batch Test Runner")
    print("=" * 78)

    if not TEST_DIR.exists():
        print(
            f"❌ 测试目录不存在: {TEST_DIR}"
        )
        sys.exit(1)

    case_files = sorted(
        TEST_DIR.glob("*.json")
    )

    if not case_files:
        print(
            f"⚠ 当前没有测试文件: {TEST_DIR}"
        )
        print(
            "请先在 tests/query_plan/ "
            "中创建测试 JSON。"
        )
        return

    try:
        registries = build_registries()

    except Exception as e:
        print(
            f"❌ Registry 加载失败: {e}"
        )
        sys.exit(1)

    total = 0
    passed = 0
    failed = 0

    category_stats = {}

    for path in case_files:
        total += 1

        print()
        print("-" * 78)
        print(f"测试文件: {path.name}")

        try:
            case_data = load_case(path)

        except Exception as e:
            print(
                f"❌ 测试文件 JSON 读取失败: {e}"
            )
            failed += 1
            continue

        case_id = case_data.get(
            "case_id",
            path.stem
        )

        category = case_data.get(
            "category",
            "unknown"
        )

        description = case_data.get(
            "description",
            ""
        )

        plan = case_data.get("plan")

        if plan is None:
            print(
                "❌ 测试文件缺少 plan 字段"
            )
            failed += 1
            continue

        category_stats.setdefault(
            category,
            {
                "total": 0,
                "passed": 0,
            }
        )

        category_stats[category][
            "total"
        ] += 1

        temp_plan_path = (
            TEST_DIR
            / f".__tmp_{case_id}.json"
        )

        try:
            with temp_plan_path.open(
                "w",
                encoding="utf-8"
            ) as f:
                json.dump(
                    plan,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            validator_result = validate_plan(
                temp_plan_path,
                registries,
            )

        finally:
            if temp_plan_path.exists():
                temp_plan_path.unlink()

        problems = check_expected_result(
            case_data,
            validator_result,
        )

        print(f"Case ID: {case_id}")
        print(f"Category: {category}")

        if description:
            print(
                f"Description: {description}"
            )

        if validator_result["errors"]:
            print(
                "Validator Errors:"
            )

            for error in validator_result[
                "errors"
            ]:
                print(
                    f"  [{error['code']}] "
                    f"{error['path']} "
                    f"{error.get('message', '')}"
                )

        if validator_result["warnings"]:
            print(
                "Validator Warnings:"
            )

            for warning in validator_result[
                "warnings"
            ]:
                print(
                    f"  [{warning['code']}] "
                    f"{warning['path']} "
                    f"{warning.get('message', '')}"
                )

        if problems:
            failed += 1

            print("❌ 测试失败")

            for problem in problems:
                print(f"  - {problem}")

        else:
            passed += 1
            category_stats[
                category
            ]["passed"] += 1

            print("✅ 测试通过")

    print()
    print("=" * 78)
    print("测试汇总")
    print("=" * 78)

    print(f"总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")

    if total > 0:
        rate = passed / total * 100
        print(
            f"通过率: {rate:.2f}%"
        )

    print()
    print("分类统计:")

    for category, stats in sorted(
        category_stats.items()
    ):
        category_total = stats["total"]
        category_passed = stats["passed"]

        rate = (
            category_passed
            / category_total
            * 100
        )

        print(
            f"  {category}: "
            f"{category_passed}/"
            f"{category_total} "
            f"({rate:.2f}%)"
        )

    print("=" * 78)

    if failed == 0:
        print(
            "✅ 当前所有 Query Plan 测试通过"
        )
    else:
        print(
            "❌ 当前存在未通过测试"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
