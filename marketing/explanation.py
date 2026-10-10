from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class ExplanationLayer:
    def explain(self, decision: Any) -> dict[str, Any]:
        data = decision.to_dict() if hasattr(decision, "to_dict") else (asdict(decision) if is_dataclass(decision) else dict(decision))
        evidence = data.get("evidence") or data.get("matched_rules") or []
        return {
            "decision_id": data.get("tag_id") or data.get("segment_id") or data.get("opportunity_id") or data.get("strategy_id"),
            "decision_type": self._type(data),
            "customer_id": data.get("customer_id"),
            "rule_version": data.get("rule_version"),
            "rule_source": data.get("rule_source"),
            "time_range": data.get("time_range"),
            "evidence": evidence,
            "facts": data.get("facts", []),
            "rule_decisions": data.get("rule_decisions", []),
            "suggestions": data.get("suggestions", []),
            "statement": data.get("explanation") or "该结果由配置化规则和 Stage 6 安全结果共同产生。",
        }

    @staticmethod
    def _type(data: dict[str, Any]) -> str:
        for key, name in (("tag_id", "tag"), ("segment_id", "segment"), ("opportunity_id", "opportunity"), ("strategy_id", "strategy")):
            if key in data:
                return name
        return "unknown"
