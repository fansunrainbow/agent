from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from query_plan.models import QueryPlan


class PlannerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    plan: QueryPlan | None = None
    mode: Literal["deterministic", "provider"] = "deterministic"
    grounded_ids: dict[str, list[str]] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    raw_output: dict[str, Any] | None = None

