from __future__ import annotations

from typing import Any

from agent.models import ClarificationQuestion, ClarificationResult


class ClarificationEngine:
    """Turn grounded ambiguities and validator failures into precise questions."""

    UNSUPPORTED_CODES = {
        "UNKNOWN_INTENT",
        "UNSUPPORTED_CAPABILITY",
        "UNSUPPORTED_INTENT",
        "MULTI_FACT_JOIN_NOT_ALLOWED",
    }

    @staticmethod
    def _question_for_error(error: dict[str, Any]) -> ClarificationQuestion:
        code = str(error.get("code", "VALIDATION_ERROR"))
        value = error.get("value")
        path = error.get("path")
        messages = {
            "UNKNOWN_METRIC": "该指标未在指标注册表中。请改用已注册指标或补充明确的业务口径。",
            "UNKNOWN_DIMENSION": "该维度未在维度注册表中。请说明希望使用的已注册分析维度。",
            "UNKNOWN_CONCEPT": "该业务概念未在词典中。请明确筛选规则，不要只使用模糊业务词。",
            "UNKNOWN_ENTITY_TYPE": "该实体类型当前未注册，无法安全解析。",
            "MISSING_REQUIRED_TIME_RANGE": f"指标“{value}”依赖统计期间，缺少时间时不能安全执行。请补充日期范围、月份或季度。",
            "LOW_CONFIDENCE": "当前解析置信度不足，请补充更明确的指标、范围或筛选条件。",
        }
        return ClarificationQuestion(
            code=code,
            question=messages.get(code, error.get("message") or "当前请求无法唯一解释，请补充明确条件。"),
            term=str(value) if value is not None else None,
            path=path,
        )

    def from_plan_and_validation(
        self,
        plan: dict[str, Any] | None,
        validation: dict[str, Any] | None,
        fallback_message: str | None = None,
        grounded_conditions: list[Any] | None = None,
    ) -> ClarificationResult:
        questions: list[ClarificationQuestion] = []
        for item in (plan or {}).get("ambiguities", []):
            questions.append(ClarificationQuestion(
                code=f"AMBIGUOUS_{str(item.get('type', 'other')).upper()}",
                question=item.get("question") or item.get("reason") or "请进一步明确该条件。",
                term=item.get("term"),
                options=item.get("candidates", []),
            ))
        errors = (validation or {}).get("errors", [])
        questions.extend(self._question_for_error(error) for error in errors)
        unsupported = any(error.get("code") in self.UNSUPPORTED_CODES for error in errors)
        unsupported_types = {"prediction_request", "suitability_request", "unsupported_attribute"}
        unsupported_conditions = [
            item for item in (grounded_conditions or [])
            if getattr(item, "status", None) == "unsupported" and getattr(item, "semantic_type", None) in unsupported_types
        ]
        for item in unsupported_conditions:
            questions.append(ClarificationQuestion(
                code=item.target or "UNSUPPORTED_CAPABILITY",
                question=item.question or item.reason or "当前能力不支持该请求。",
                term=item.original_surface,
                options=item.candidates,
            ))
        unsupported = unsupported or bool(unsupported_conditions)
        if not questions and fallback_message:
            questions.append(ClarificationQuestion(code="PLANNER_ERROR", question=fallback_message))
        deduped = []
        seen = set()
        for question in questions:
            key = (question.code, question.question, question.term)
            if key not in seen:
                seen.add(key)
                deduped.append(question)
        return ClarificationResult(
            needed=bool(deduped) and not unsupported,
            questions=deduped,
            unsupported=unsupported,
            message=(unsupported_conditions[0].reason if unsupported_conditions else "当前能力不支持该请求。") if unsupported else None,
        )
