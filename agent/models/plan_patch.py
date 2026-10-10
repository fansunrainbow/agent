from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PatchOperation(StrEnum):
    ADD_FILTER = "ADD_FILTER"
    REMOVE_FILTER = "REMOVE_FILTER"
    REPLACE_FILTER = "REPLACE_FILTER"
    ADD_METRIC = "ADD_METRIC"
    REMOVE_METRIC = "REMOVE_METRIC"
    REPLACE_METRIC = "REPLACE_METRIC"
    CHANGE_TIME_RANGE = "CHANGE_TIME_RANGE"
    REMOVE_TIME_RANGE = "REMOVE_TIME_RANGE"
    CHANGE_ORDER = "CHANGE_ORDER"
    REMOVE_ORDER = "REMOVE_ORDER"
    CHANGE_LIMIT = "CHANGE_LIMIT"
    REMOVE_LIMIT = "REMOVE_LIMIT"
    ADD_DIMENSION = "ADD_DIMENSION"
    REMOVE_DIMENSION = "REMOVE_DIMENSION"
    REPLACE_DIMENSION = "REPLACE_DIMENSION"


class PlanPatch(BaseModel):
    """One explicit, auditable mutation against a parent Query Plan."""

    model_config = ConfigDict(extra="forbid")

    operation: PatchOperation
    target: str = Field(min_length=1)
    old_value: Any = None
    new_value: Any = None
    requested_new_value: Any = None
    resolution_status: Literal["resolved", "ambiguous", "not_found", "unsupported"] = "resolved"
    patch_status: Literal["APPLIED", "NEEDS_CLARIFICATION", "UNSUPPORTED", "FAILED"] = "APPLIED"
    source: str = "explicit_follow_up"

    def to_change(self) -> dict[str, Any]:
        return {
            "action": self.operation.value,
            "patch_operation": self.operation.value,
            "target": self.target,
            "patch_target": self.target,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "requested_new_value": self.requested_new_value if self.requested_new_value is not None else self.new_value,
            "resolution_status": self.resolution_status,
            "patch_status": self.patch_status,
            "value": self.new_value,
            "source": self.source,
        }
