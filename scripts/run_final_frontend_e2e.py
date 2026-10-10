from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseConfig

DatabaseConfig.from_env()

from webapp.api import app


def main() -> int:
    cases = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in (ROOT / "benchmark/datasets/real_db_gold.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    client = TestClient(app)
    results: list[dict] = []

    def chat(name: str, case_id: str, conversation_id: str | None = None) -> dict:
        payload = {"message": cases[case_id]["query"], "conversation_id": conversation_id, "execute": True}
        response = client.post("/api/chat", json=payload)
        value = response.json()
        visible_payload = all(key in value for key in ("query_plan", "sql", "params", "guardrail", "result", "trace"))
        results.append({
            "scenario": name, "case_id": case_id, "http_status": response.status_code,
            "mode": value.get("mode"), "agent_status": value.get("status"),
            "real_execution_requested": True, "required_payload_fields_present": visible_payload,
            "query_id": value.get("query_id"),
        })
        return value

    health = client.get("/api/health").json()
    chat("1. 南京客户有多少", "RDB_S01")
    chat("2. 2026 Q1 南京客户日均资产", "RDB_M01")
    chat("3. 复杂四条件筛选", "RDB_C06")
    chat("4. 双 Metric", "RDB_M14")
    chat("5. Product Category", "RDB_M15")
    chat("6. Branch Filter", "RDB_M16")
    chat("7. Ranking / Top-K", "RDB_M11")
    first = chat("8a. Multi-turn base", "RDB_M01")
    follow = client.post("/api/chat", json={"message": "改成苏州。", "conversation_id": first.get("conversation_id"), "execute": True}).json()
    results.append({"scenario": "8b. Multi-turn Patch", "mode": follow.get("mode"), "agent_status": follow.get("status"), "same_conversation": follow.get("conversation_id") == first.get("conversation_id"), "required_payload_fields_present": all(key in follow for key in ("query_plan", "sql", "params", "guardrail", "result", "trace"))})
    profile = client.get("/api/customer/C000000000000001/profile").json()
    results.append({"scenario": "9. Customer 360", "mode": profile.get("mode"), "agent_status": profile.get("status"), "available": profile.get("status") == "success", "message": profile.get("message")})
    opportunity = client.get("/api/opportunities?customer_id=C000000000000001").json()
    results.append({"scenario": "10. Marketing Opportunity", "mode": opportunity.get("mode"), "agent_status": opportunity.get("status"), "available": opportunity.get("status") == "success", "message": opportunity.get("message")})
    clarification = client.post("/api/chat", json={"message": "筛选日均资产超过50万的客户。", "execute": True}).json()
    results.append({"scenario": "11. Clarification", "mode": clarification.get("mode"), "agent_status": clarification.get("status"), "passed": clarification.get("status") == "needs_clarification"})
    unsupported = client.post("/api/chat", json={"message": "预测客户下月收益", "execute": True}).json()
    results.append({"scenario": "12. Unsupported", "mode": unsupported.get("mode"), "agent_status": unsupported.get("status"), "passed": unsupported.get("status") == "unsupported"})
    trace_source = next((item for item in results if item.get("query_id")), {})
    trace = client.get(f"/api/query/{trace_source.get('query_id')}/trace").json() if trace_source else {}
    results.append({"scenario": "13. Guardrail Trace", "mode": health.get("mode"), "trace_available": bool(trace.get("trace"))})

    source = (ROOT / "frontend/src/main.jsx").read_text(encoding="utf-8")
    ui = {
        "mode_badge_can_show_real_db": "mode?.startsWith('REAL')" in source,
        "chat_requests_real_execution": "execute:mode==='REAL_DB'" in source.replace(" ", ""),
        "query_plan_visible": "<PlanCard plan={current?.query_plan}" in source,
        "sql_visible": "current?.sql" in source,
        "params_visible": "current?.params" in source,
        "guardrail_visible": "<Guardrail data={current?.guardrail}" in source,
        "result_visible": "current?.result ?? null" in source,
        "trace_visible": "last?.trace" in source,
        "customer_360_available": "api(`/api/customer/" in source,
        "marketing_available": "api(`/api/opportunities?" in source,
        "benchmark_dashboard_available": "api('/api/benchmark/summary')" in source,
    }
    scenario_failures = [
        item["scenario"] for item in results
        if item.get("agent_status") in {"error", "blocked", "requires_real_db", "customer_required", "query_failed", "db_unavailable", "not_found"}
        or item.get("required_payload_fields_present") is False
        or item.get("available") is False
        or item.get("passed") is False
        or item.get("same_conversation") is False
        or item.get("trace_available") is False
    ]
    report = {
        "status": "PASS" if all(ui.values()) and not scenario_failures else "FAIL",
        "health": health,
        "scenario_count": len(results),
        "scenarios": results,
        "ui_verification": ui,
        "blocking_reasons": ([f"Scenario failed: {name}" for name in scenario_failures]
                             + ([] if all(ui.values()) else ["One or more required UI capabilities are missing."])),
    }
    output = ROOT / "benchmark/reports/real_db_final/frontend_real_db_e2e.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "health": health, "scenario_count": len(results), "ui_verification": ui}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
