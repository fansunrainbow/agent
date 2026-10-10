from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Opportunity:
    opportunity_id: str
    name: str
    customer_id: str
    priority: str
    matched_rules: list[dict[str, Any]]
    actual_values: dict[str, Any]
    thresholds: dict[str, Any]
    threshold_sources: dict[str, str]
    time_range: dict[str, Any] | None
    rule_version: str
    rule_source: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
