from pathlib import Path
import json
import yaml


ROOT = Path(__file__).resolve().parents[1]

METRICS_FILE = ROOT / "metadata" / "metrics.yaml"
TEST_DIR = ROOT / "tests" / "query_plan"

TEST_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 基础读取
# ============================================================

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 获取全部已注册 Metric
# ============================================================

def extract_metric_ids(metrics_data):
    metrics = metrics_data.get("metrics", {})

    if isinstance(metrics, dict):
        return set(metrics.keys())

    if isinstance(metrics, list):
        result = set()

        for item in metrics:
            if isinstance(item, str):
                result.add(item)

            elif isinstance(item, dict):
                if "metric_id" in item:
                    result.add(str(item["metric_id"]))

                elif "id" in item:
                    result.add(str(item["id"]))

        return result

    return set()


# ============================================================
# 获取测试中已经使用的 Metric
# ============================================================

def walk_filter_nodes(node):
    if not isinstance(node, dict):
        return

    if "logic" in node:
        for child in node.get("conditions", []):
            yield from walk_filter_nodes(child)
    else:
        yield node


def collect_used_metrics():
    used = set()

    for path in TEST_DIR.glob("*.json"):
        try:
            case_data = load_json(path)
        except Exception:
            continue

        plan = case_data.get("plan", {})

        # metrics
        for metric in plan.get("metrics", []):
            used.add(metric)

        # filter / having 中的 metric
        for section in ("filters", "having"):
            for node in plan.get(section, []):
                for item in walk_filter_nodes(node):
                    if item.get("type") == "metric":
                        target = item.get("target")

                        if target:
                            used.add(target)

        # order_by 中可能直接使用 metric
        for item in plan.get("order_by", []):
            field = item.get("field")

            if field:
                used.add(field)

    return used


# ============================================================
# 判断 Metric 是否建议带时间范围
# ============================================================

def needs_time_range(metric_id):
    """
    Coverage 测试阶段使用保守策略：
    对资产、交易、资金流、持仓、变化、收益等指标
    默认给一个明确 Q1 时间范围。

    即使部分指标可以做最新时点查询，
    给明确时间范围也不会引入模糊时间假设。
    """

    keywords = [
        "asset",
        "trade",
        "buy",
        "sell",
        "inflow",
        "outflow",
        "holding",
        "profit",
        "change",
        "ratio",
        "balance",
        "amount",
        "count",
        "value",
    ]

    metric_lower = metric_id.lower()

    return any(
        keyword in metric_lower
        for keyword in keywords
    )


# ============================================================
# 构造标准 Query Plan
# ============================================================

def make_plan(metric_id):
    time_range = None

    if needs_time_range(metric_id):
        time_range = {
            "type": "quarter",
            "year": 2026,
            "quarter": 1
        }

    return {
        "version": "1.0",
        "status": "ready",
        "intent": "metric_query",
        "subject": "customer",

        "metrics": [
            metric_id
        ],

        "dimensions": [],

        "filters": [],

        "entities": [],

        "time_range": time_range,

        "group_by": [],

        "having": [],

        "order_by": [],

        "limit": None,

        "output": {
            "mode": "summary",
            "format": "table",
            "include_details": False,
            "include_explanation": True
        },

        "ambiguities": [],

        "assumptions": [],

        "confidence": {
            "overall": 1.0,
            "intent": 1.0,
            "metrics": 1.0,
            "dimensions": 1.0,
            "entities": 1.0,
            "time": 1.0,
            "filters": 1.0
        },

        "context": {
            "parent_plan_id": None,
            "operation": "new"
        }
    }


# ============================================================
# 主程序
# ============================================================

def main():
    metrics_data = load_yaml(METRICS_FILE)

    registered_metrics = extract_metric_ids(
        metrics_data
    )

    used_metrics = collect_used_metrics()

    uncovered_metrics = sorted(
        registered_metrics - used_metrics
    )

    print("=" * 78)
    print("Metric Coverage Case Generator")
    print("=" * 78)

    print(
        f"注册 Metric 数量: "
        f"{len(registered_metrics)}"
    )

    print(
        f"已经覆盖 Metric 数量: "
        f"{len(registered_metrics & used_metrics)}"
    )

    print(
        f"未覆盖 Metric 数量: "
        f"{len(uncovered_metrics)}"
    )

    print()

    if not uncovered_metrics:
        print(
            "✅ 当前所有注册 Metric 都已经有测试覆盖"
        )
        return

    print("未覆盖 Metric:")

    for metric in uncovered_metrics:
        print(f"  - {metric}")

    print()

    # 从 X100 开始，避免和前面的 X001-X011 冲突
    start_index = 100

    created = 0

    for offset, metric_id in enumerate(
        uncovered_metrics
    ):
        case_id = f"MX{start_index + offset:03d}"

        case_data = {
            "case_id": case_id,
            "category": "Metric-Coverage",

            "description": (
                f"补充 Metric Coverage: {metric_id}"
            ),

            "input": (
                f"查询标准指标 {metric_id}。"
            ),

            "plan": make_plan(
                metric_id
            ),

            "expected": {
                "valid": True,
                "error_codes": []
            }
        }

        filename = (
            f"{case_id}_"
            f"{metric_id}.json"
        )

        path = TEST_DIR / filename

        with path.open(
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                case_data,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"✅ 创建: {filename}"
        )

        created += 1

    print()
    print("=" * 78)

    print(
        f"✅ 共创建 {created} 条 "
        f"Metric Coverage 测试"
    )

    print("=" * 78)


if __name__ == "__main__":
    main()