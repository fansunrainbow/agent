from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SegmentResult:
    segment_id: str
    name: str
    matched_customer_ids: list[str]
    customer_count: int
    rule: dict[str, Any]
    threshold_sources: dict[str, str]
    time_range: dict[str, Any] | None
    evidence: dict[str, list[dict[str, Any]]]
    rule_version: str
    rule_source: str
    excluded_due_to_missing: list[str] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
