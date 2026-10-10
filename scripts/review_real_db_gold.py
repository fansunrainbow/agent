from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseConfig, create_readonly_connection


DEFAULT_CASES = ROOT / "benchmark" / "datasets" / "real_db_gold.jsonl"
DEFAULT_REPORT_DIR = ROOT / "benchmark" / "reports" / "real_db_final"
ALLOWED_REVIEW_FIELDS = {
    "review_status", "reviewed_at", "review_method", "review_note", "reject_reason"
}
WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|CALL|GRANT|REVOKE|LOAD|INTO\s+OUTFILE)\b",
    re.IGNORECASE,
)

PRIORITY_CASES = {"RDB_S05", "RDB_C06", "RDB_C07", "RDB_M11", "RDB_M12", "RDB_C10"}
BRANCH_CASES = {"RDB_S05", "RDB_M16", "RDB_C05", "RDB_C11"}
PRODUCT_CASES = {"RDB_M06", "RDB_M07", "RDB_M08", "RDB_M15", "RDB_C01", "RDB_C02", "RDB_C05", "RDB_C08"}
DICTIONARY_CASES = {
    "RDB_S03", "RDB_S04", "RDB_S05", "RDB_M02", "RDB_M06", "RDB_M07", "RDB_M08",
    "RDB_M10", "RDB_M15", "RDB_M16", "RDB_C01", "RDB_C03", "RDB_C05", "RDB_C06",
    "RDB_C08", "RDB_C11", "RDB_C12",
}
MULTI_FACT_CASES = {"RDB_M14", "RDB_C01", "RDB_C02", "RDB_C03", "RDB_C04", "RDB_C11"}
TIME_SERIES_CASES = {"RDB_M13"}
RANKING_DETAILS = {
    "RDB_M11": {"sort": "average_total_asset DESC", "tie_breaker": "pty_id ASC"},
    "RDB_M12": {"sort": "trade_amount DESC", "tie_breaker": "pty_id ASC"},
    "RDB_C10": {"sort": "trade_amount DESC", "tie_breaker": "t.pty_id ASC"},
}

COMPLEX_DETAILS: dict[str, dict[str, str]] = {
    "RDB_C01": {
        "tables": "ads_cust_info_d, dwd_cust_hold_d, dim_product, dws_cust_fin_d",
        "metrics": "fund_holding_ratio, net_inflow",
        "dimensions": "city, gender, product_primary_category",
        "join_path": "customer -> holding -> product category; customer -> finance (facts pre-aggregated by pty_id)",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "holding ratio and net inflow per customer",
        "group_by": "holding.pty_id; finance.pty_id",
        "having": "none (outer WHERE applies ratio < 0.1 and net_inflow > 0)",
        "order_by": "customer.pty_id ASC", "limit": "none",
    },
    "RDB_C02": {
        "tables": "dws_cust_aset_d, dwd_cust_tran_d, dim_product",
        "metrics": "average_total_asset, stock_trade_amount",
        "dimensions": "product_primary_category",
        "join_path": "asset aggregate -> customer <- stock trade aggregate",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "asset / 90 natural days and stock trades per customer",
        "group_by": "asset.pty_id; trade.pty_id",
        "having": "none (outer WHERE applies both thresholds)",
        "order_by": "pty_id ASC", "limit": "none",
    },
    "RDB_C03": {
        "tables": "ads_cust_info_d, dws_cust_fin_d, dws_cust_aset_d",
        "metrics": "net_inflow, asset_change",
        "dimensions": "customer_level",
        "join_path": "customer -> finance aggregate; customer -> asset endpoint aggregate",
        "time_range": "finance Q1; assets 2026-01-01 and 2026-03-31",
        "aggregation": "net flow sum; end asset minus start asset",
        "group_by": "finance.pty_id; asset.pty_id",
        "having": "none (outer WHERE applies negative metrics)",
        "order_by": "pty_id ASC", "limit": "none",
    },
    "RDB_C04": {
        "tables": "ads_cust_info_d, dws_cust_aset_d, dwd_cust_tran_d",
        "metrics": "average_total_asset, trade_amount",
        "dimensions": "city",
        "join_path": "city customers -> asset aggregate and trade aggregate independently",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "customer daily asset then population average; total trade sum",
        "group_by": "asset.pty_id", "having": "none", "order_by": "none", "limit": "none",
    },
    "RDB_C05": {
        "tables": "dwd_cust_tran_d, ads_cust_info_d, dim_branch, dim_product",
        "metrics": "stock_trade_amount",
        "dimensions": "branch, product_primary_category",
        "join_path": "trade -> customer -> branch; trade -> product category (semi-join)",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "total stock trade amount",
        "group_by": "none", "having": "none", "order_by": "none", "limit": "none",
    },
    "RDB_C06": {
        "tables": "ads_cust_info_d, dws_cust_fin_d",
        "metrics": "net_inflow",
        "dimensions": "city, gender, customer_level, customer_status",
        "join_path": "customer -> finance aggregate",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "net inflow per customer",
        "group_by": "finance.pty_id", "having": "none", "order_by": "pty_id ASC", "limit": "none",
    },
    "RDB_C07": {
        "tables": "ads_cust_info_d", "metrics": "customer_count",
        "dimensions": "city, age, gender", "join_path": "none",
        "time_range": "current customer snapshot", "aggregation": "COUNT(DISTINCT pty_id)",
        "group_by": "none", "having": "none", "order_by": "none", "limit": "none",
    },
    "RDB_C08": {
        "tables": "ads_cust_info_d, dwd_cust_hold_d", "metrics": "customer set",
        "dimensions": "city, product", "join_path": "customer NOT EXISTS holding for product",
        "time_range": "2026-01-01 .. 2026-03-31", "aggregation": "none",
        "group_by": "none", "having": "none", "order_by": "pty_id ASC", "limit": "none",
    },
    "RDB_C09": {
        "tables": "ads_cust_info_d", "metrics": "customer_count", "dimensions": "city",
        "join_path": "none", "time_range": "current customer snapshot",
        "aggregation": "COUNT(DISTINCT pty_id) per city", "group_by": "city_name",
        "having": "customer_count > 2", "order_by": "city_name ASC", "limit": "none",
    },
    "RDB_C10": {
        "tables": "dwd_cust_tran_d, ads_cust_info_d", "metrics": "trade_amount",
        "dimensions": "city, customer", "join_path": "trade -> customer",
        "time_range": "2026-01-01 .. 2026-03-31", "aggregation": "trade amount per customer",
        "group_by": "trade.pty_id", "having": "none",
        "order_by": "trade_amount DESC, pty_id ASC", "limit": "10",
    },
    "RDB_C11": {
        "tables": "ads_cust_info_d, dim_branch, dws_cust_aset_d, dwd_cust_tran_d, dws_cust_fin_d",
        "metrics": "average_total_asset, trade_amount, net_inflow", "dimensions": "branch",
        "join_path": "branch customers -> asset, trade, finance aggregates independently",
        "time_range": "2026-01-01 .. 2026-03-31",
        "aggregation": "customer daily asset then average; total trades; total net flow",
        "group_by": "asset.pty_id", "having": "none", "order_by": "none", "limit": "none",
    },
    "RDB_C12": {
        "tables": "ads_cust_info_d, dws_cust_aset_d", "metrics": "cash_asset_ratio",
        "dimensions": "age, gender, customer_status", "join_path": "customer -> end-date asset",
        "time_range": "end date 2026-03-31", "aggregation": "row-level end-date ratio",
        "group_by": "none", "having": "none", "order_by": "pty_id ASC", "limit": "none",
    },
}


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_normalize(value: Any) -> Any:
    value = normalize(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = Decimal(str(value))
        if number == 0:
            number = Decimal(0)
        return {"__number__": format(number.normalize(), "f")}
    if isinstance(value, dict):
        return {key: digest_normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [digest_normalize(item) for item in value]
    return value


def stable_digest(rows: list[dict[str, Any]], unordered: bool = True) -> str:
    encoded = [stable_json(digest_normalize(row)) for row in rows]
    if unordered:
        encoded.sort()
    return hashlib.sha256(("\n".join(encoded) + ("\n" if encoded else "")).encode("utf-8")).hexdigest()


def values_equal(left: Any, right: Any, absolute: float = 0.01, relative: float = 1e-9) -> bool:
    left, right = normalize(left), normalize(right)
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), abs_tol=absolute, rel_tol=relative)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            values_equal(left[key], right[key], absolute, relative) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            values_equal(a, b, absolute, relative) for a, b in zip(left, right)
        )
    return left == right


def compare_results(case: dict[str, Any], current: Any) -> bool:
    stored = normalize(case["gold_result"])
    current = normalize(current)
    tolerance = case.get("numeric_tolerance") or {}
    absolute = float(tolerance.get("absolute", 0.01))
    relative = float(tolerance.get("relative", 1e-9))
    kind = case.get("expected_result_type") or case.get("comparison_kind")
    if kind in {"set", "grouped", "time_series"}:
        key = stable_json
        stored = sorted(stored, key=key)
        current = sorted(current, key=key)
    return values_equal(stored, current, absolute, relative)


def classify_result(result_type: str, rows: list[dict[str, Any]], value: Any) -> str:
    if result_type == "scalar":
        if not rows or value is None:
            return "no_record"
        if isinstance(value, (int, float, Decimal)) and float(value) == 0:
            return "zero"
        return "value"
    return "empty_set" if not rows else "non_empty_set"


def validate_gold_sql(sql: str) -> None:
    compact = sql.strip().rstrip(";").strip()
    if not compact or not re.match(r"^(SELECT|WITH)\b", compact, re.IGNORECASE):
        raise ValueError("Gold SQL must start with SELECT or WITH")
    if ";" in compact:
        raise ValueError("Multiple SQL statements are not allowed")
    if WRITE_WORDS.search(compact):
        raise ValueError("Non-read-only keyword found in Gold SQL")


def ranking_ambiguity(case: dict[str, Any]) -> bool:
    if case.get("expected_result_type") != "ranking":
        return False
    detail = RANKING_DETAILS.get(case["case_id"], {})
    tie_breaker = detail.get("tie_breaker", "")
    sql = re.sub(r"\s+", " ", case.get("gold_sql", "")).lower()
    tokens = [token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*\s+(?:ASC|DESC)", tie_breaker)]
    return not tie_breaker or not tokens or not all(token in sql for token in tokens)


def warnings_for(case_id: str) -> list[str]:
    warnings: list[str] = []
    mappings = (
        (PRIORITY_CASES, "PRIORITY_MANUAL_REVIEW"),
        (BRANCH_CASES, "BRANCH_CASE"),
        (PRODUCT_CASES, "PRODUCT_CASE"),
        (DICTIONARY_CASES, "DICTIONARY_MAPPING_CASE"),
        (MULTI_FACT_CASES, "MULTI_FACT_CASE"),
        (TIME_SERIES_CASES, "TIME_SERIES_CASE"),
    )
    for cases, label in mappings:
        if case_id in cases:
            warnings.append(label)
    return warnings


def time_context(case: dict[str, Any]) -> list[str]:
    sql = case.get("gold_sql", "")
    result: list[str] = []
    if "20260101" in sql and "20260331" in sql and "BETWEEN" in sql.upper():
        result.append("2026 Q1: 2026-01-01 .. 2026-03-31")
    if ("dws_cust_aset_d" in sql or "dwd_cust_hold_d" in sql) and re.search(r"data_dt\s+BETWEEN", sql, re.IGNORECASE):
        result.append("asset/holding calendar mode: natural_calendar_days")
    if "dwd_cust_tran_d" in sql or "dws_cust_fin_d" in sql:
        result.append("trade/flow calendar mode: observed trading-day rows only; no synthetic date padding")
    dates = sorted(set(re.findall(r"data_dt\s*=\s*'([0-9]{8})'", sql, re.IGNORECASE)))
    if dates:
        result.append("snapshot/end date(s): " + ", ".join(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates))
    return result or ["time scope: current snapshot / not applicable"]


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(cases) != 40:
        raise ValueError(f"Expected 40 Gold cases, found {len(cases)}")
    ids = [case.get("case_id") for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case_id in Gold dataset")
    for case in cases:
        if not case.get("gold_sql") or "gold_result" not in case:
            raise ValueError(f"{case.get('case_id')} is missing gold_sql/gold_result")
    return cases


def select_cases(cases: list[dict[str, Any]], case_arg: str | None, difficulty: str | None, pending_only: bool) -> list[dict[str, Any]]:
    selected = cases
    if case_arg:
        normalized = case_arg.strip().upper()
        if not normalized.startswith("RDB_"):
            normalized = "RDB_" + normalized
        selected = [case for case in selected if case["case_id"].upper() == normalized]
        if not selected:
            raise ValueError(f"Unknown case: {case_arg}")
    if difficulty:
        selected = [case for case in selected if case.get("difficulty") == difficulty]
    if pending_only:
        selected = [
            case for case in selected
            if case.get("review_status") in {"pending", "pending_after_correction"}
        ]
    return selected


def execute_gold(connection: Any, case: dict[str, Any]) -> dict[str, Any]:
    validate_gold_sql(case["gold_sql"])
    started = perf_counter()
    cursor = connection.raw_connection.cursor()
    try:
        cursor.execute(case["gold_sql"])
        columns = [entry[0] for entry in cursor.description or []]
        rows = [normalize(dict(zip(columns, row))) for row in cursor.fetchall()]
    finally:
        cursor.close()
    latency_ms = round((perf_counter() - started) * 1000, 3)
    result_type = case["expected_result_type"]
    current_result = next(iter(rows[0].values())) if result_type == "scalar" and rows else None
    if result_type != "scalar":
        current_result = rows
    return {
        "gold_execution_success": True,
        "gold_execution_latency_ms": latency_ms,
        "stored_gold_result": normalize(case["gold_result"]),
        "current_gold_result": current_result,
        "gold_result_match": compare_results(case, current_result),
        "result_classification": classify_result(result_type, rows, current_result),
        "row_count": len(rows),
    }


def print_result(label: str, result_type: str, value: Any, show_full: bool) -> None:
    print(f"\n{label}:")
    if result_type == "scalar":
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    rows = normalize(value or [])
    unordered = result_type in {"set", "grouped", "time_series"}
    ordered = sorted(rows, key=stable_json) if unordered else rows
    print(f"  count: {len(rows)}")
    print(f"  SHA-256: {stable_digest(rows, unordered=unordered)}")
    if show_full or (result_type in {"grouped", "time_series", "ranking"} and len(rows) <= 50):
        shown = ordered
    else:
        shown = ordered[:10]
        if len(rows) > 10:
            print("  preview: first 10 stable rows (use --show-full-result for all rows)")
    print(json.dumps(shown, ensure_ascii=False, indent=2))


def print_case(case: dict[str, Any], audit: dict[str, Any], show_full: bool) -> None:
    print("\n" + "=" * 88)
    flags = warnings_for(case["case_id"])
    print(f"CASE {case['case_id']}" + (f"  !!! {' | '.join(flags)} !!!" if flags else ""))
    print("=" * 88)
    print(f"Difficulty       : {case['difficulty']}")
    print(f"Natural Language: {case['query']}")
    print(f"Intent           : {case['intent']}")
    print(f"Result Type      : {case['expected_result_type']}")
    print(f"Gold Source      : {case['gold_source']}")
    print(f"Review Status    : {case.get('review_status', 'pending')}")
    print("Time Context     : " + "\n                   ".join(time_context(case)))
    print(f"Gold SQL         : {case['gold_sql']}")

    if case["case_id"] in COMPLEX_DETAILS:
        print("\nComplex SQL review context:")
        for key, value in COMPLEX_DETAILS[case["case_id"]].items():
            print(f"  {key.replace('_', ' ').title():12}: {value}")

    if case["case_id"] in RANKING_DETAILS:
        detail = RANKING_DETAILS[case["case_id"]]
        print("\nRanking rule:")
        print(f"  Sort field/direction: {detail['sort']}")
        print(f"  Tie breaker        : {detail['tie_breaker']}")
        print(f"  Ambiguity          : {'GOLD_RANKING_TIE_AMBIGUITY' if audit['ranking_ambiguity'] else 'NO'}")

    print_result("Stored Gold Result", case["expected_result_type"], case["gold_result"], show_full)
    if audit.get("gold_execution_success"):
        print_result("Current DB Result", case["expected_result_type"], audit["current_gold_result"], show_full)
    print("\nGold SQL re-execution:")
    print(f"  success       : {audit.get('gold_execution_success', False)}")
    print(f"  latency_ms    : {audit.get('gold_execution_latency_ms')}")
    print(f"  result class  : {audit.get('result_classification', 'unknown')}")
    print(f"  stored/current: {'MATCH' if audit.get('gold_result_match') else 'GOLD_DRIFT'}")
    if audit.get("error"):
        print(f"  error         : {audit['error']}")


def save_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    content = "\n".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) for case in cases) + "\n"
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def apply_review(case: dict[str, Any], action: str, note: str) -> None:
    original = {key: value for key, value in case.items() if key not in ALLOWED_REVIEW_FIELDS}
    now = datetime.now(timezone.utc).isoformat()
    if action == "approve":
        case.update(review_status="reviewed", reviewed_at=now, review_method="human_manual", review_note=note)
        case.pop("reject_reason", None)
    elif action == "reject":
        case.update(
            review_status="rejected", reviewed_at=now, review_method="human_manual",
            review_note=note, reject_reason=note,
        )
    else:
        raise ValueError(f"Unknown review action: {action}")
    current = {key: value for key, value in case.items() if key not in ALLOWED_REVIEW_FIELDS}
    if original != current:
        raise RuntimeError("Review attempted to modify immutable Gold fields")


def read_previous_audits(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {item["case_id"]: item for item in payload.get("cases", [])}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def write_summary(cases: list[dict[str, Any]], audits: dict[str, dict[str, Any]], report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    status_path = report_dir / "gold_review_status.json"
    previous = read_previous_audits(status_path)
    entries: list[dict[str, Any]] = []
    for case in cases:
        old = previous.get(case["case_id"], {})
        audit = audits.get(case["case_id"], {})
        execution_success = audit.get("gold_execution_success", old.get("gold_execution_success"))
        result_match = audit.get("gold_result_match", old.get("gold_result_match"))
        entry = {
            "case_id": case["case_id"],
            "difficulty": case["difficulty"],
            "review_status": case.get("review_status", "pending"),
            "gold_execution_success": execution_success,
            "gold_execution_latency_ms": audit.get("gold_execution_latency_ms", old.get("gold_execution_latency_ms")),
            "stored_gold_result": audit.get("stored_gold_result", old.get("stored_gold_result")),
            "current_gold_result": audit.get("current_gold_result", old.get("current_gold_result")),
            "gold_result_match": result_match,
            "gold_drift": execution_success is True and result_match is False,
            "ranking_ambiguity": ranking_ambiguity(case),
            "result_classification": audit.get("result_classification", old.get("result_classification")),
            "row_count": audit.get("row_count", old.get("row_count")),
            "last_gold_audit_at": audit.get("audited_at", old.get("last_gold_audit_at")),
        }
        if audit.get("error"):
            entry["gold_execution_error"] = audit["error"]
        elif old.get("gold_execution_error") and not audit:
            entry["gold_execution_error"] = old["gold_execution_error"]
        entries.append(entry)
    counts = {
        "reviewed": sum(case.get("review_status") == "reviewed" for case in cases),
        "pending": sum(case.get("review_status", "pending") in {"pending", "pending_after_correction"} for case in cases),
        "rejected": sum(case.get("review_status") == "rejected" for case in cases),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(cases),
        **counts,
        "gold_drift": sum(item["gold_drift"] for item in entries),
        "ranking_ambiguity": sum(item["ranking_ambiguity"] for item in entries),
        "cases": entries,
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    corrections = [
        case for case in cases
        if case.get("review_status") == "rejected" and case.get("reject_reason", "").strip().upper() == "GOLD_ERROR"
    ]
    corrections_path = report_dir / "gold_corrections_required.jsonl"
    corrections_path.write_text(
        "".join(json.dumps({
            "case_id": case["case_id"], "query": case["query"], "review_status": "rejected",
            "reason": "GOLD_ERROR", "review_note": case.get("review_note"),
            "recorded_at": case.get("reviewed_at"),
        }, ensure_ascii=False) + "\n" for case in corrections),
        encoding="utf-8",
    )
    return payload


def prompt_action(case: dict[str, Any], audit: dict[str, Any]) -> tuple[str, str | None]:
    blocked = (
        not audit.get("gold_execution_success")
        or not audit.get("gold_result_match")
        or audit.get("ranking_ambiguity")
    )
    while True:
        answer = input("\n[A]pprove / [R]eject / [S]kip / [Q]uit: ").strip().lower()
        aliases = {"a": "approve", "approve": "approve", "r": "reject", "reject": "reject", "s": "skip", "skip": "skip", "q": "quit", "quit": "quit"}
        action = aliases.get(answer)
        if not action:
            print("Invalid action. Enter A, R, S, or Q.")
            continue
        if action == "approve" and blocked:
            print("Approve blocked: execution failure, GOLD_DRIFT, or GOLD_RANKING_TIE_AMBIGUITY requires manual resolution.")
            continue
        if action == "approve":
            while True:
                note = input("Human review note (required): ").strip()
                if note:
                    return action, note
                print("A non-empty human review note is required.")
        if action == "reject":
            while True:
                reason = input("Reject reason (use GOLD_ERROR when Gold SQL/result is wrong): ").strip()
                if reason:
                    return action, reason
                print("A non-empty reject reason is required.")
        return action, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Human review runner for independently-authored Real DB Gold SQL")
    parser.add_argument("--case", help="Single case, for example C01 or RDB_C01")
    parser.add_argument("--difficulty", choices=("simple", "medium", "complex"))
    parser.add_argument("--pending-only", action="store_true")
    parser.add_argument("--show-full-result", action="store_true")
    parser.add_argument("--audit-only", action="store_true", help="Re-execute and compare Gold SQL without review prompts or dataset writes")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cases = load_cases(args.cases)
    selected = select_cases(cases, args.case, args.difficulty, args.pending_only)
    if not selected:
        print("No cases matched the filters.")
        summary = write_summary(cases, {}, args.report_dir)
        print(json.dumps({key: summary[key] for key in ("total", "reviewed", "pending", "rejected", "gold_drift", "ranking_ambiguity")}, ensure_ascii=False, indent=2))
        return 0

    config = DatabaseConfig.from_env()
    if config.user != "agent_readonly_user":
        raise SystemExit(f"Refusing Gold review: DB_USER must be agent_readonly_user, got {config.user!r}")
    connection = create_readonly_connection(config)
    audits: dict[str, dict[str, Any]] = {}
    exit_code = 0
    try:
        capability = connection.capability_check()
        if not capability.readonly_verified:
            raise SystemExit("Read-only capability verification failed")
        connection.set_session(readonly=True)
        connection.set_statement_timeout(config.query_timeout)
        print(f"Read-only DB verified: user={config.user}, database={config.name}, selected_cases={len(selected)}")

        for case in selected:
            try:
                audit = execute_gold(connection, case)
            except Exception as exc:
                audit = {
                    "gold_execution_success": False,
                    "gold_execution_latency_ms": None,
                    "stored_gold_result": normalize(case["gold_result"]),
                    "current_gold_result": None,
                    "gold_result_match": False,
                    "result_classification": "execution_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                exit_code = 1
            audit["ranking_ambiguity"] = ranking_ambiguity(case)
            audit["audited_at"] = datetime.now(timezone.utc).isoformat()
            audits[case["case_id"]] = audit
            print_case(case, audit, args.show_full_result)

            if args.audit_only:
                continue
            action, note = prompt_action(case, audit)
            if action == "quit":
                break
            if action == "skip":
                continue
            apply_review(case, action, note or "")
            save_cases(args.cases, cases)
            print(f"Saved human decision: {case['case_id']} -> {case['review_status']}")
    finally:
        connection.close()
        summary = write_summary(cases, audits, args.report_dir)
        print("\nGold Review Summary")
        print(json.dumps({key: summary[key] for key in ("total", "reviewed", "pending", "rejected", "gold_drift", "ranking_ambiguity")}, ensure_ascii=False, indent=2))
        print(f"Status file: {args.report_dir / 'gold_review_status.json'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
