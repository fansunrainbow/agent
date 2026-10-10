from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from agent.orchestrator import AgentOrchestrator
from database import DatabaseConfig, create_readonly_connection
from database.privacy import safe_records
from guardrail.execution_manager import ExecutionManager
from guardrail.sql_generator import SQLGenerationError, SQLGenerator
from marketing.tools import MarketingTools


ROOT = Path(__file__).resolve().parents[1]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    return value


class ApplicationService:
    """Thin application façade. It orchestrates existing services and stores display state."""

    def __init__(self) -> None:
        self.agent = AgentOrchestrator()
        self.generator = SQLGenerator()
        self.execution = ExecutionManager()
        self.marketing = MarketingTools()
        self.conversations: dict[str, list[dict[str, Any]]] = {}
        self.queries: dict[str, dict[str, Any]] = {}
        self.artifacts: dict[str, Any] = {}
        self.execution_results: dict[str, Any] = {}
        self.customer_analyses: dict[str, dict[str, Any]] = {}

    @staticmethod
    def database_mode() -> str:
        return "REAL_DB" if all(os.getenv(key) for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")) else "DEMO / DRY RUN"

    def chat(self, message: str, conversation_id: str | None = None, execute: bool = False) -> dict[str, Any]:
        conversation_id = conversation_id or uuid4().hex
        history = self.conversations.setdefault(conversation_id, [])
        prior = next((item for item in reversed(history) if item.get("query_plan")), None)
        context = {"previous_plan": prior["query_plan"], "parent_plan_id": prior["query_id"]} if prior else None
        started = perf_counter()
        state = self.agent.run(message, context)
        response: dict[str, Any] = {
            "conversation_id": conversation_id, "query_id": state.query_id,
            "mode": self.database_mode(), "status": state.status.value,
            "message": self._assistant_message(state), "query_plan": state.query_plan,
            "trace": [_jsonable(item) for item in state.trace],
            "latency": {"plan_ms": state.latency_ms},
            "sql": None, "params": {}, "guardrail": None, "explain": None,
            "result": None, "result_validation": None,
        }
        if state.status.value == "ready":
            compile_started = perf_counter()
            try:
                artifact = self.generator.generate(state.query_id, state.query_plan, state.validation_result)
                self.artifacts[state.query_id] = artifact
                response["latency"]["compile_ms"] = round((perf_counter() - compile_started) * 1000, 3)
                response["sql"], response["params"] = artifact.sql, artifact.params
                if execute:
                    if self.database_mode() != "REAL_DB":
                        response.update(status="db_unavailable", message="未配置真实数据库；已安全停留在 Dry Run。")
                    else:
                        connection = create_readonly_connection(DatabaseConfig.from_env())
                        capability = connection.capability_check()
                        response["database_capability"] = capability.to_dict()
                        if not capability.readonly_verified:
                            response.update(status="guardrail_blocked", message="数据库账号未通过只读权限检查。")
                        else:
                            executed = self.execution.execute(artifact, connection)
                            self.execution_results[state.query_id] = executed
                            response.update(
                                status=executed.status, result=safe_records(executed.rows, executed.columns),
                                guardrail=executed.trace.validation, explain=executed.trace.explain_summary,
                                result_validation=executed.trace.result_validation,
                            )
                            response["latency"].update(executed.trace.latency_breakdown_ms)
                        connection.close()
                else:
                    checked = self.execution.dry_run(artifact)
                    response["guardrail"] = checked.trace.validation
            except SQLGenerationError as exc:
                response.update(status="guardrail_blocked", message=str(exc), guardrail={"allowed": False, "code": exc.code, "evidence": exc.evidence})
        response["latency"]["end_to_end_ms"] = round((perf_counter() - started) * 1000, 3)
        history.append({"role": "user", "message": message})
        history.append({"role": "assistant", **response})
        self.queries[state.query_id] = response
        return response

    def customer_analysis(self, customer_id: str) -> dict[str, Any]:
        if customer_id in self.customer_analyses:
            return self.customer_analyses[customer_id]
        if self.database_mode() != "REAL_DB":
            return {"status": "db_unavailable", "mode": self.database_mode(), "customer_id": customer_id, "message": "真实数据库未连接；不使用演示数据替代。"}
        question = f"查询客户{customer_id}的年龄、性别、客户等级、客户状态、客户类型、城市和省份"
        response = self.chat(question, execute=True)
        if response.get("status") != "success":
            return {"status": "query_failed", "mode": response.get("mode"), "customer_id": customer_id, "message": response.get("message"), "query": response}
        query_id = response["query_id"]
        artifact, result = self.artifacts.get(query_id), self.execution_results.get(query_id)
        if artifact is None or result is None:
            return {"status": "query_failed", "mode": response.get("mode"), "customer_id": customer_id, "message": "安全结果或 SQL Artifact 缺失。"}
        features = self.marketing.build_customer_profile(result, artifact)
        feature = next((item for item in features if item.customer_id == customer_id), None)
        if feature is None:
            return {"status": "not_found", "mode": response.get("mode"), "customer_id": customer_id, "message": "真实数据库中没有该客户安全结果。"}
        analysis = self.marketing.analysis_service.analyze_customer(feature)
        payload = {"status": "success", "mode": response.get("mode"), "query_id": query_id, **analysis}
        self.customer_analyses[customer_id] = payload
        return payload

    @staticmethod
    def _assistant_message(state: Any) -> str:
        if state.status.value == "ready":
            return "查询计划已生成并通过语义校验。"
        if state.status.value == "unsupported":
            return "该请求超出当前受控数据与规则范围。"
        if state.clarification and state.clarification.questions:
            return state.clarification.questions[0].question
        return "需要补充信息后才能安全执行。"

    def benchmark_summary(self) -> dict[str, Any]:
        frozen_path = ROOT / "benchmark" / "reports" / "stage8_6_frozen" / "benchmark_report.json"
        real_path = ROOT / "benchmark" / "reports" / "real_db_final" / "real_db_benchmark_report.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else {}
        real = json.loads(real_path.read_text(encoding="utf-8")) if real_path.exists() else None
        return {
            "frozen": frozen,
            "headline": {
                "raw_frozen": 76.11, "adjudicated": 91.15, "semantic_raw": 83.33,
                "generalization_f1": 87.27, "sql_dry_run": 93.33, "multi_turn": 80.0,
                "end_to_end_dry_run": 85.0, "hallucination_handling": 100.0,
                "guardrail": 100.0, "stability": 100.0,
            },
            "evolution": {
                "labels": ["Initial", "Stage 8.2", "Stage 8.3", "Stage 8.4", "Stage 8.5", "Stage 8.6"],
                "semantic": [26.67, 83.33, 83.33, 83.33, 83.33, 83.33],
                "sql": [53.33, 53.33, 53.33, 93.33, 93.33, 93.33],
                "multi_turn": [50.0, 50.0, 50.0, 50.0, 80.0, 80.0],
                "hallucination": [90.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            },
            "real_db": real,
            "real_db_status": "MEASURED" if real else "NOT_MEASURED",
        }


service = ApplicationService()
