from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class StrategyResult:
    customer_id: str
    strategy_id: str
    name: str
    facts: list[dict[str, Any]]
    rule_decisions: list[dict[str, Any]]
    suggestions: list[dict[str, Any]]
    prohibited_actions: list[str]
    rule_version: str
    rule_source: str
    time_range: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
