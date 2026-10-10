from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "query_plan"
OUTPUT = ROOT / "benchmark" / "datasets"


def write(name: str, cases: list[dict[str, Any]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"{name}.jsonl"
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in cases), encoding="utf-8")


def source_case(prefix: str) -> dict[str, Any]:
    path = next(SOURCE.glob(f"{prefix}_*.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def leaves(nodes: list[dict[str, Any]]):
    for node in nodes:
        if "logic" in node:
            yield from leaves(node.get("conditions", []))
        else:
            yield node


def semantic_case(prefix: str, suite_prefix: str, source: str = "self_built") -> dict[str, Any]:
    raw = source_case(prefix)
    plan = raw["plan"]
    expected = {
        "intent": plan.get("intent"), "status": plan.get("status"),
        "metrics": plan.get("metrics", []), "dimensions": plan.get("dimensions", []),
        "operators": sorted({item.get("operator") for item in leaves(plan.get("filters", [])) if item.get("operator")}),
        "time_range": plan.get("time_range"),
        "entities": sorted(str(item.get("resolved", {}).get("id")) for item in plan.get("entities", []) if item.get("resolved")),
        "entity_types": sorted({item.get("entity_type") for item in plan.get("entities", []) if item.get("entity_type")}),
    }
    return {
        "case_id": f"{suite_prefix}_{prefix}", "category": "semantic", "query": raw["input"],
        "expected": expected, "difficulty": "simple" if prefix.startswith("S") else "medium",
        "source": source, "tags": [raw["category"].lower(), prefix.lower()],
    }


def plan_case(prefix: str, suite_prefix: str, source: str = "self_built") -> dict[str, Any]:
    raw = source_case(prefix)
    return {
        "case_id": f"{suite_prefix}_{prefix}", "category": "query_plan", "query": raw["input"],
        "expected": {"plan": raw["plan"]},
        "difficulty": "complex" if prefix.startswith(("C", "MX")) else "medium",
        "source": source, "tags": [raw["category"].lower(), prefix.lower()],
    }


def marketing_case(case_id: str, target: str, features: dict[str, Any], expected: dict[str, Any], rule_id: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {"target": target, "customer_id": "MASKED-CUSTOMER", "features": features}
    if rule_id:
        payload["rule_id"] = rule_id
    payload.update(extra)
    return {
        "case_id": case_id, "category": "marketing", "input": payload, "expected": expected,
        "difficulty": "medium", "source": "human_reviewed" if int(case_id.split("_")[-1]) <= 20 else "self_built",
        "tags": [target, rule_id or "policy"],
    }


def build_official() -> list[dict[str, Any]]:
    rows = [
        ("学历本科及以上的男性客户，年龄大于50岁的有多少个", ["customer_count"], ["education", "gender", "age"], None),
        ("不同客户年龄段资产分布情况，如下规则：1、小于30 2、大于等于30，小于50 3、大于等于50，小于60 4、大于60", ["total_asset"], ["age_group"], None),
        ("钻石卡男性客户，年龄大于40岁，持有比亚迪市值超过1000元，他在26年Q1的盈亏情况", ["asset_profit"], ["customer_level", "gender", "age"], {"type": "quarter", "year": 2026, "quarter": 1}),
        ("分公司各营业部的客户省份分析统计", ["customer_count"], ["parent_branch", "branch", "province"], None),
        ("26年Q1交易过招商银行，且26年Q1末普通账户持有中国平安的客户", [], ["customer_type"], {"type": "quarter", "year": 2026, "quarter": 1}),
        ("26年Q1日均资产大于30万的客户，股票交易量大于10万的，其持有的产品属于哪些产品大类", ["average_total_asset", "stock_trade_amount"], ["product_category"], {"type": "quarter", "year": 2026, "quarter": 1}),
        ("查询26年1月10日到26年2月15日期间，科创板交易量大于25万的客户营业部分布情况", ["stock_trade_amount"], ["market", "branch"], {"type": "date_range", "start_date": "2026-01-10", "end_date": "2026-02-15"}),
    ]
    return [{
        "case_id": f"OFFICIAL_{i:03d}", "category": "official_seed", "query": query,
        "expected": {"metrics": metrics, "dimensions": dims, "time_range": time_range},
        "difficulty": "complex", "source": "official_seed", "tags": ["official_qna", "seed_only"],
    } for i, (query, metrics, dims, time_range) in enumerate(rows, 1)]


def build_semantic() -> list[dict[str, Any]]:
    cases = [semantic_case(f"S{i:03d}", "SEM") for i in range(1, 21)]
    cases += [semantic_case(f"M{i:03d}", "SEM") for i in range(1, 6)]
    cases += [semantic_case(prefix, "SEM") for prefix in ("E001", "E004", "E005", "E006", "E009")]
    return cases


def build_plans() -> list[dict[str, Any]]:
    return [plan_case(f"M{i:03d}", "PLAN") for i in range(11, 21)] + [plan_case(f"C{i:03d}", "PLAN") for i in range(1, 21)]


def build_generalization() -> list[dict[str, Any]]:
    cases = [plan_case(f"MX{i:03d}", "GEN", "generalization") for i in range(100, 121)]
    cases += [plan_case(f"X{i:03d}", "GEN", "generalization") for i in range(1, 10)]
    return cases


def build_sql() -> list[dict[str, Any]]:
    prefixes = ["S001", "S003", "S010", "S012", "S015", "S019", "M001", "M002", "M005", "M006", "M008", "M013", "M014", "C002", "C010"]
    result = []
    for prefix in prefixes:
        raw = source_case(prefix)
        result.append({
            "case_id": f"SQL_{prefix}", "category": "sql", "input": {"plan": raw["plan"]},
            "expected": {"compile_success": True, "schema_valid": True, "join_valid": True, "parameterized_values": True, "guard_allowed": True},
            "difficulty": "complex" if prefix.startswith("C") else "medium", "source": "self_built", "tags": ["dry_run", "parameterized"],
        })
    return result


def build_results() -> list[dict[str, Any]]:
    fixtures = [
        ("scalar", 42, 42, 0), ("scalar", 0, 0, 0), ("aggregation", 1250000.0, 1250000.01, 0.001),
        ("aggregation", 18, 18, 0), ("set", ["A", "B"], ["B", "A"], 0),
        ("set", [], [], 0), ("ranking", ["C1", "C2", "C3"], ["C1", "C2", "C3"], 0),
        ("ranking", ["P1"], ["P1"], 0), ("grouped", {"南京": 10, "苏州": 8}, {"苏州": 8, "南京": 10}, 0),
        ("grouped", {"男": 11.0, "女": 9.0}, {"男": 11.001, "女": 9.0}, 0.01),
        ("scalar", -5, -5, 0), ("set", ["股票", "基金", "债券"], ["债券", "股票", "基金"], 0),
    ]
    return [{
        "case_id": f"RESULT_{i:03d}", "category": "result", "input": {"actual": actual},
        "expected": {"result_type": kind, "value": expected, "tolerance": tolerance},
        "difficulty": "simple", "source": "self_built", "tags": [kind, "synthetic_fixture"],
    } for i, (kind, expected, actual, tolerance) in enumerate(fixtures, 1)]


def build_guardrail() -> list[dict[str, Any]]:
    unsafe = [
        "DROP TABLE dim_product", "DELETE FROM ads_cust_info_d", "UPDATE ads_cust_info_d SET city_name = :p1",
        "INSERT INTO ads_cust_info_d (pty_id) VALUES (:p1)", "ALTER TABLE dim_product ADD x INT", "TRUNCATE TABLE dim_product",
        "SELECT * FROM ads_cust_info_d AS c", "SELECT g.pty_id FROM ghost_customer AS g",
        "SELECT c.ghost_col FROM ads_cust_info_d AS c", "SELECT c.pty_id FROM ads_cust_info_d AS c JOIN dws_cust_aset_d AS a ON c.pty_id = a.data_dt WHERE a.data_dt = :p1",
        "SELECT t.pty_id FROM dwd_cust_tran_d AS t", "SELECT c.pty_id FROM ads_cust_info_d AS c WHERE c.city_name = '南京'",
        "SELECT c.pty_id FROM ads_cust_info_d AS c; DROP TABLE dim_product", "SELECT SLEEP(:p1) FROM ads_cust_info_d AS c",
        "SELECT c.pty_id FROM ads_cust_info_d AS c -- hidden", "SELECT c.pty_id FROM ads_cust_info_d AS c LIMIT 1000001",
        "CREATE TABLE x (id INT)",
    ]
    safe = [
        "SELECT c.pty_id FROM ads_cust_info_d AS c WHERE c.city_name = :p1",
        "SELECT c.city_name, COUNT(c.pty_id) FROM ads_cust_info_d AS c WHERE c.city_name = :p1 GROUP BY c.city_name",
        "SELECT t.pty_id, SUM(t.buy_amt) FROM dwd_cust_tran_d AS t WHERE t.data_dt BETWEEN :p1 AND :p2 GROUP BY t.pty_id",
    ]
    result = []
    for i, sql in enumerate(unsafe + safe, 1):
        action = "block" if i <= len(unsafe) else "allow"
        result.append({"case_id": f"GUARD_{i:03d}", "category": "guardrail", "input": {"sql": sql}, "expected": {"action": action}, "difficulty": "adversarial" if action == "block" else "simple", "source": "adversarial" if action == "block" else "self_built", "tags": [action, "sql_guard"]})
    return result


def build_marketing() -> list[dict[str, Any]]:
    specs = [
        ("tags", {"average_total_asset": 1200000}, {"ids": ["high_asset"]}, None),
        ("tags", {"cash_asset_ratio": .6}, {"ids": ["high_cash_ratio"]}, None),
        ("tags", {"stock_holding_ratio": .6}, {"ids": ["stock_preference"]}, None),
        ("tags", {"fund_holding_ratio": .05}, {"ids": ["fund_low_allocation"]}, None),
        ("tags", {"trade_count": 30}, {"ids": ["trade_active"]}, None),
        ("tags", {"net_inflow": 1}, {"ids": ["net_inflow"]}, None),
        ("tags", {"net_inflow": -1}, {"ids": ["net_outflow"]}, None),
        ("tags", {"asset_change_rate": .1}, {"ids": ["asset_growth"]}, None),
        ("tags", {"asset_change_rate": -.1}, {"ids": ["asset_decline"]}, None),
        ("segment", {"average_total_asset": 1200000, "fund_holding_ratio": .05}, {"matched": True}, "high_asset_low_fund"),
        ("segment", {"customer_level": "1000001", "net_inflow": -1, "asset_change_rate": -.1}, {"matched": True}, "high_level_outflow_decline"),
        ("segment", {"fund_holding_ratio": .05}, {"matched": True}, "fund_low_allocation"),
        ("segment", {"net_inflow": 1}, {"matched": True}, "positive_flow_or_growth"),
        ("segment", {"trade_count": 25, "net_inflow": 0}, {"matched": True}, "active_non_outflow"),
        ("opportunities", {"average_total_asset": 1200000, "fund_holding_ratio": .05}, {"ids": ["fund_allocation_opportunity"]}, None),
        ("opportunities", {"cash_asset_ratio": .6, "wealth_management_holding_ratio": .05}, {"ids": ["cash_allocation_opportunity"]}, None),
        ("opportunities", {"trade_count": 30, "stock_holding_ratio": .85}, {"ids": ["active_concentrated_trading"]}, None),
        ("opportunities", {"customer_level": "1000001", "net_inflow": -1}, {"ids": ["high_level_outflow_attention"]}, None),
        ("opportunities", {"asset_change_rate": -.1, "net_inflow": -1}, {"ids": ["asset_decline_outflow_attention"]}, None),
        ("opportunities", {"net_inflow": 600000}, {"ids": ["large_recent_inflow_followup"]}, None),
        ("strategies", {"average_total_asset": 1200000, "fund_holding_ratio": .05}, {"ids": ["improve_fund_allocation"]}, None),
        ("strategies", {"cash_asset_ratio": .6, "wealth_management_holding_ratio": .05}, {"ids": ["optimize_asset_allocation"]}, None),
        ("strategies", {"trade_count": 30, "stock_holding_ratio": .85}, {"ids": ["discuss_product_structure"]}, None),
        ("strategies", {"customer_level": "1000001", "net_inflow": -1}, {"ids": ["maintain_high_level_customer"]}, None),
        ("explanation", {"average_total_asset": 1200000, "fund_holding_ratio": .05}, {"required_fields": ["decision_id", "decision_type", "customer_id", "rule_version", "rule_source", "time_range", "evidence", "statement"], "required_evidence_fields": ["feature_id", "operator", "actual_value", "threshold", "source", "time_range"]}, "fund_allocation_opportunity"),
        ("explanation", {"customer_level": "1000001", "net_inflow": -1}, {"required_fields": ["decision_id", "decision_type", "customer_id", "rule_version", "rule_source", "evidence", "statement"], "required_evidence_fields": ["feature_id", "passed", "threshold_source"]}, "high_level_outflow_attention"),
    ]
    cases = [marketing_case(f"MKT_{i:03d}", target, features, expected, rule_id) for i, (target, features, expected, rule_id) in enumerate(specs, 1)]
    cases.append(marketing_case("MKT_027", "segment", {"average_total_asset": 1200000, "fund_holding_ratio": None}, {"matched": False, "excluded_due_to_missing": True}, "high_asset_low_fund", missing_states={"fund_holding_ratio": "unknown"}))
    ranges = {"average_total_asset": {"type": "quarter", "year": 2026, "quarter": 1}, "fund_holding_ratio": {"type": "quarter", "year": 2026, "quarter": 2}}
    cases.append(marketing_case("MKT_028", "segment", {"average_total_asset": 1200000, "fund_holding_ratio": .05}, {"matched": False, "time_conflict": True}, "high_asset_low_fund", feature_time_ranges=ranges))
    cases.append(marketing_case("MKT_029", "attribute", {}, {"supported": False, "code": "UNSUPPORTED_CUSTOMER_ATTRIBUTE"}, attribute_id="risk_preference"))
    cases.append(marketing_case("MKT_030", "specific_product", {}, {"allowed": False, "code": "SUITABILITY_DATA_REQUIRED"}, product_name="某高风险产品"))
    cases.append(marketing_case("MKT_031", "strategies", {"asset_change_rate": -.1, "net_inflow": -1}, {"ids": ["monitor_asset_and_flow"]}))
    cases.append(marketing_case("MKT_032", "strategies", {"net_inflow": 600000}, {"ids": ["follow_up_recent_inflow"]}))
    return cases


def build_hallucination() -> list[dict[str, Any]]:
    queries = ["查询客户满意度评分最高的20名客户", "查询已婚客户中资产最高的20个人", "预测下个月最可能流失的客户", "推荐最适合客户购买的具体基金", "查询客户星座分布", "筛选风险偏好激进的客户", "查询社交影响力指数", "找出一定会购买产品的客户"]
    cases = [{"case_id": f"HALL_AGENT_{i:03d}", "category": "hallucination", "query": query, "input": {"mode": "agent"}, "expected": {"action": "reject"}, "difficulty": "adversarial", "source": "adversarial", "tags": ["unknown_semantic"]} for i, query in enumerate(queries, 1)]
    sqls = ["SELECT x.fake FROM ghost AS x", "SELECT c.marital_status FROM ads_cust_info_d AS c", "SELECT * FROM dim_product", "SELECT RANDOM() FROM ads_cust_info_d AS c"]
    cases += [{"case_id": f"HALL_SQL_{i:03d}", "category": "hallucination", "input": {"mode": "guardrail", "sql": sql}, "expected": {"action": "reject"}, "difficulty": "adversarial", "source": "adversarial", "tags": ["unknown_schema"]} for i, sql in enumerate(sqls, 1)]
    attrs = ["risk_preference", "purchase_intent", "churn_probability", "response_probability", "marital_status", "income_level"]
    for i, attr in enumerate(attrs, 1):
        cases.append({"case_id": f"HALL_MKT_ATTR_{i:03d}", "category": "hallucination", "input": {"mode": "marketing", "target": "attribute", "customer_id": "MASKED", "features": {}, "attribute_id": attr}, "expected": {"action": "reject", "supported": False, "code": "UNSUPPORTED_CUSTOMER_ATTRIBUTE"}, "difficulty": "adversarial", "source": "adversarial", "tags": ["unsupported_attribute"]})
    for i, product in enumerate(["产品A", "产品B"], 1):
        cases.append({"case_id": f"HALL_MKT_PRODUCT_{i:03d}", "category": "hallucination", "input": {"mode": "marketing", "target": "specific_product", "customer_id": "MASKED", "features": {}, "product_name": product}, "expected": {"action": "reject", "allowed": False, "code": "SUITABILITY_DATA_REQUIRED"}, "difficulty": "adversarial", "source": "adversarial", "tags": ["suitability"]})
    return cases


def build_multi_turn() -> list[dict[str, Any]]:
    cases = [
        (["2026年Q1南京客户平均资产是多少？", "只看钻石客户。", "换成苏州。"], ["average_total_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "苏州"}, {"type": "dimension", "target": "customer_level", "operator": "eq", "value": "1000001"}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1南京客户有多少？", "只看女性。"], ["customer_count"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "南京"}, {"type": "dimension", "target": "gender", "operator": "eq", "value": "F"}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1苏州客户日均资产是多少？", "改成Q2。"], ["average_total_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "苏州"}], {"type": "quarter", "year": 2026, "quarter": 2}),
        (["2026年Q1南京股票交易额超过10万的客户", "再加上基金持仓占比低于10%。"], ["stock_trade_amount", "fund_holding_ratio"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "南京"}, {"type": "metric", "target": "stock_trade_amount", "operator": "gt", "value": 100000}, {"type": "metric", "target": "fund_holding_ratio", "operator": "lt", "value": 0.1}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1南京客户平均资产前20名", "改成前10名。"], ["average_total_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "南京"}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1男性客户净流入为正", "去掉性别条件。"], ["net_inflow"], [{"type": "metric", "target": "net_inflow", "operator": "gt", "value": 0}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1南京客户总资产", "换成现金资产。"], ["cash_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "南京"}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1基金交易额最高的客户", "改为股票交易额。"], ["stock_trade_amount"], [], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1南京钻石客户日均资产", "换成苏州普通客户。"], ["average_total_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "苏州"}, {"type": "dimension", "target": "customer_level", "operator": "eq", "value": "1000003"}], {"type": "quarter", "year": 2026, "quarter": 1}),
        (["2026年Q1南京客户平均资产是多少？", "只看钻石客户。", "换成苏州。"], ["average_total_asset"], [{"type": "dimension", "target": "city", "operator": "eq", "value": "苏州"}, {"type": "dimension", "target": "customer_level", "operator": "eq", "value": "1000001"}], {"type": "quarter", "year": 2026, "quarter": 1}),
    ]
    return [{"case_id": f"MT_{i:03d}", "category": "multi_turn", "turns": turns, "expected": {"status": "ready", "metrics": metrics, "filters": filters, "time_range": time_range}, "difficulty": "complex", "source": "generalization", "tags": ["context_patch", "stability"], "repeat": 3 if i in {1, 10} else 1} for i, (turns, metrics, filters, time_range) in enumerate(cases, 1)]


def build_e2e() -> list[dict[str, Any]]:
    ready = [source_case(f"S{i:03d}")["input"] for i in [1, 3, 10, 12, 15, 19]] + [source_case(f"M{i:03d}")["input"] for i in [1, 2, 5, 6, 8, 13, 14]]
    clarify = ["筛选日均资产超过50万的客户。", "帮我找近期比较活跃的优质客户。", "查询客户满意度评分最高的20名客户。", "查询已婚客户中资产最高的20个人。", "查询一个不存在的业务指标", "查找风险偏好最高的客户", "预测客户下月收益"]
    cases = [{"case_id": f"E2E_READY_{i:03d}", "category": "end_to_end", "query": query, "expected": {"status": "ready"}, "difficulty": "medium", "source": "self_built", "tags": ["dry_run", "trace"]} for i, query in enumerate(ready, 1)]
    cases += [{"case_id": f"E2E_CLARIFY_{i:03d}", "category": "end_to_end", "query": query, "expected": {"status": "needs_clarification"}, "difficulty": "adversarial", "source": "generalization", "tags": ["clarification", "unsupported"]} for i, query in enumerate(clarify, 1)]
    return cases


def main() -> None:
    datasets = {
        "official_seed": build_official(), "semantic": build_semantic(), "query_plan": build_plans(),
        "sql": build_sql(), "result": build_results(), "guardrail": build_guardrail(),
        "marketing": build_marketing(), "hallucination": build_hallucination(),
        "generalization": build_generalization(), "multi_turn": build_multi_turn(), "end_to_end": build_e2e(),
    }
    for name, cases in datasets.items():
        write(name, cases)
    write("human_reviewed_marketing", datasets["marketing"][:20])
    print(json.dumps({name: len(cases) for name, cases in datasets.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
