from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RuleEvidence:
    feature_id: str
    feature_kind: str
    actual_value: Any
    operator: str
    threshold: Any
    passed: bool | None
    source: str
    threshold_source: str
    time_range: dict[str, Any] | None
    missing_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CustomerTag:
    tag_id: str
    name: str
    customer_id: str
    matched: bool
    status: str
    evidence: list[RuleEvidence]
    parameters: dict[str, Any]
    threshold_sources: dict[str, str]
    rule_version: str
    rule_source: str
    time_range: dict[str, Any] | None
    explanation: str
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "evidence": [item.to_dict() for item in self.evidence],
        }
