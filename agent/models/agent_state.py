from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .clarification_result import ClarificationResult
from .grounded_condition import GroundedCondition


class AgentStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    REPAIRABLE = "repairable"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"
    ERROR = "error"


class TraceEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    step: str
    status: str
    source: str | None = None
    input_summary: Any = None
    output_summary: Any = None
    latency_ms: float | None = None


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(default_factory=lambda: uuid4().hex)
    user_query: str = Field(min_length=1)
    conversation_context: dict[str, Any] = Field(default_factory=dict)
    routed_tools: list[str] = Field(default_factory=list)
    grounded_conditions: list[GroundedCondition] = Field(default_factory=list)
    retrieved_metrics: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_dimensions: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_concepts: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    resolved_entities: list[dict[str, Any]] = Field(default_factory=list)
    grounding_sources: list[dict[str, Any]] = Field(default_factory=list)
    query_plan: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    repair_count: int = Field(default=0, ge=0, le=2)
    repair_history: list[dict[str, Any]] = Field(default_factory=list)
    clarification: ClarificationResult | None = None
    clarification_needed: bool = False
    status: AgentStatus = AgentStatus.PROCESSING
    trace: list[TraceEntry] = Field(default_factory=list)
    latency_ms: float | None = None

    def add_trace(self, step: str, status: str, **details: Any) -> None:
        self.trace.append(TraceEntry(step=step, status=status, **details))
