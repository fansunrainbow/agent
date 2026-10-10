from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


MissingState = Literal["observed", "zero", "no_record", "unknown"]
FeatureKind = Literal["metric", "dimension"]


@dataclass
class FeatureValue:
    feature_id: str
    kind: FeatureKind
    value: Any
    time_range: dict[str, Any] | None
    source: str
    confidence: float
    missing_state: MissingState

    @property
    def usable(self) -> bool:
        return self.missing_state in {"observed", "zero"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CustomerFeature:
    customer_id: str
    features: dict[str, FeatureValue]
    source_metrics: list[str]
    source_dimensions: list[str]
    attribute_snapshot_date: str | None
    metric_time_range: dict[str, Any] | None
    confidence: float
    trace: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def get(self, feature_id: str) -> FeatureValue | None:
        return self.features.get(feature_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "features": {key: value.to_dict() for key, value in self.features.items()},
        }
