from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Difficulty = Literal["simple", "medium", "complex", "adversarial"]
Source = Literal["official_seed", "self_built", "generalization", "adversarial", "human_reviewed"]


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    query: str | None = None
    turns: list[str] | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any]
    difficulty: Difficulty
    source: Source
    tags: list[str] = Field(default_factory=list)
    repeat: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def require_query_or_input(self) -> "BenchmarkCase":
        if not self.query and not self.turns and not self.input:
            raise ValueError("case requires query, turns, or input")
        return self


class CaseOutcome(BaseModel):
    case_id: str
    suite: str
    passed: bool
    score: float = Field(ge=0, le=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    failure_type: str | None = None
    stage: str | None = None
    trace_id: str | None = None
    notes: str | None = None
    case_input: dict[str, Any] = Field(default_factory=dict)


FAILURE_TYPES = {
    "SEMANTIC_ERROR", "ENTITY_RESOLUTION_ERROR", "TIME_PARSE_ERROR", "PLAN_ERROR",
    "VALIDATION_ERROR", "SQL_GENERATION_ERROR", "SCHEMA_GUARD_ERROR", "JOIN_ERROR",
    "COST_GUARD_ERROR", "EXECUTION_ERROR", "RESULT_ERROR", "MARKETING_RULE_ERROR",
    "CLARIFICATION_ERROR", "CONTEXT_ERROR", "UNSUPPORTED_HANDLING_ERROR",
}
