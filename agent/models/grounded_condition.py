from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GroundedCondition(BaseModel):
    """One independently grounded semantic condition from the user surface."""

    model_config = ConfigDict(extra="forbid")

    condition_id: str
    original_surface: str = Field(min_length=1)
    semantic_type: Literal[
        "metric", "dimension", "concept", "entity", "time", "operator", "value",
        "prediction_request", "suitability_request", "unsupported_attribute",
    ]
    target: str | None = None
    operator: str | None = None
    value: Any = None
    source: str
    confidence: float = Field(ge=0, le=1)
    status: Literal["resolved", "ambiguous", "unsupported"] = "resolved"
    candidates: list[Any] = Field(default_factory=list)
    reason: str | None = None
    question: str | None = None
    scope: str | None = None
    patch_action: Literal[
        "ADD_FILTER", "REMOVE_FILTER", "REPLACE_FILTER",
        "ADD_METRIC", "REMOVE_METRIC", "REPLACE_METRIC",
        "CHANGE_TIME_RANGE", "CHANGE_ORDER", "CHANGE_LIMIT",
    ] | None = None
