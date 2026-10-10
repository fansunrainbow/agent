from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests" / "query_plan"

TEST_DIR.mkdir(parents=True, exist_ok=True)


def make_plan(
    intent,
    metrics,
    dimensions,
    group_by,
    time_range=None,
):
    return {
        "version": "1.0",
        "status": "ready",
        "intent": intent,
        "subject": "customer",

        "metrics": metrics,
        "dimensions": dimensions,

        "filters": [],
        "entities": [],

        "time_range": time_range,

        "group_by": group_by,
        "having": [],
        "order_by": [],
        "limit": None,

        "output": {
            "mode": "aggregate",
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


cases = [
    {
        "case_id": "X003",
        "category": "Coverage",
        "description": "覆盖 age_group 维度",
        "input": "按年龄段统计客户人数。",
        "plan": make_plan(
            "group_analysis",
            ["customer_count"],
            ["age_group"],
            ["age_group"]
        )
    },

    {
        "case_id": "X004",
        "category": "Coverage",
        "description": "覆盖 customer 维度",
        "input": "按客户查看总资产。",
        "plan": make_plan(
            "group_analysis",
            ["total_asset"],
            ["customer"],
            ["customer"]
        )
    },

    {
        "case_id": "X005",
        "category": "Coverage",
        "description": "覆盖 customer_type 维度",
        "input": "按客户类型统计客户人数。",
        "plan": make_plan(
            "group_analysis",
            ["customer_count"],
            ["customer_type"],
            ["customer_type"]
        )
    },

    {
        "case_id": "X006",
        "category": "Coverage",
        "description": "覆盖 market 维度",
        "input": "按市场统计持仓市值。",
        "plan": make_plan(
            "group_analysis",
            ["holding_market_value"],
            ["market"],
            ["market"]
        )
    },

    {
        "case_id": "X007",
        "category": "Coverage",
        "description": "覆盖 month 维度",
        "input": "查看2026年各月总资产变化。",
        "plan": make_plan(
            "trend_analysis",
            ["total_asset"],
            ["month"],
            ["month"],
            {
                "type": "year",
                "year": 2026
            }
        )
    },

    {
        "case_id": "X008",
        "category": "Coverage",
        "description": "覆盖 product 维度",
        "input": "按产品统计持仓市值。",
        "plan": make_plan(
            "group_analysis",
            ["holding_market_value"],
            ["product"],
            ["product"]
        )
    },

    {
        "case_id": "X009",
        "category": "Coverage",
        "description": "覆盖 product_secondary_category 维度",
        "input": "按产品二级分类统计持仓市值。",
        "plan": make_plan(
            "group_analysis",
            ["holding_market_value"],
            ["product_secondary_category"],
            ["product_secondary_category"]
        )
    },

    {
        "case_id": "X010",
        "category": "Coverage",
        "description": "覆盖 profession 维度",
        "input": "按职业统计客户人数。",
        "plan": make_plan(
            "group_analysis",
            ["customer_count"],
            ["profession"],
            ["profession"]
        )
    },

    {
        "case_id": "X011",
        "category": "Coverage",
        "description": "覆盖 quarter 维度",
        "input": "查看2026年各季度总资产变化。",
        "plan": make_plan(
            "trend_analysis",
            ["total_asset"],
            ["quarter"],
            ["quarter"],
            {
                "type": "year",
                "year": 2026
            }
        )
    }
]


for case in cases:
    case["expected"] = {
        "valid": True,
        "error_codes": []
    }

    path = TEST_DIR / (
        f"{case['case_id']}_"
        f"{case['description']}.json"
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            case,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"✅ 创建: {path.name}")


print()
print("✅ 9 个 Dimension Coverage 测试创建完成")