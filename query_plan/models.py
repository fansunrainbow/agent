"""Pydantic contracts for the Stage 4 business Query Plan.

The JSON Schema files remain the language-neutral interchange contract.  These
models provide the equivalent typed Python boundary for generators, validators,
and the later SQL planning stages.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimpleFilter(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["dimension", "metric", "concept", "entity"]
    target: str = Field(min_length=1)
    operator: Literal[
        "eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in",
        "between", "contains", "starts_with", "ends_with", "exists",
        "not_exists", "is_null", "is_not_null",
    ]
    value: Any | None = None
    source: Literal[
        "explicit", "dictionary", "entity_resolution", "derived_rule",
        "context", "business_default",
    ]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_value_presence(self) -> "SimpleFilter":
        no_value = {"exists", "not_exists", "is_null", "is_not_null"}
        if self.operator not in no_value and self.value is None:
            raise ValueError(f"operator {self.operator} requires value")
        return self


class LogicFilter(StrictModel):
    logic: Literal["and", "or", "not"]
    conditions: list[FilterNode] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_not_arity(self) -> "LogicFilter":
        if self.logic == "not" and len(self.conditions) != 1:
            raise ValueError("not must contain exactly one condition")
        return self


FilterNode = SimpleFilter | LogicFilter
LogicFilter.model_rebuild()


class ResolvedEntity(StrictModel):
    id: str | int
    name: str
    entity_type: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityCandidate(StrictModel):
    id: str | int
    name: str
    score: float | None = Field(default=None, ge=0, le=1)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityRef(StrictModel):
    entity_type: Literal[
        "product", "branch", "parent_branch", "customer", "product_category"
    ]
    surface: str = Field(min_length=1)
    resolution_status: Literal["resolved", "ambiguous", "not_found"]
    resolved: ResolvedEntity | None = None
    candidates: list[EntityCandidate] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal[
        "exact_match", "fuzzy_match", "context", "manual_confirmation"
    ] | None = None

    @model_validator(mode="after")
    def validate_resolution_payload(self) -> "EntityRef":
        if self.resolution_status == "resolved":
            if self.resolved is None or self.confidence is None or self.source is None:
                raise ValueError("resolved entity requires resolved, confidence, and source")
        if self.resolution_status == "ambiguous" and len(self.candidates) < 2:
            raise ValueError("ambiguous entity requires at least two candidates")
        return self


class TimeRange(StrictModel):
    type: Literal[
        "absolute_date", "date_range", "month", "quarter", "year", "ytd",
        "last_n_days", "last_n_months", "latest", "start_of_period",
        "end_of_period",
    ]
    date: str | None = None
    start: str | None = None
    end: str | None = None
    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    quarter: int | None = Field(default=None, ge=1, le=4)
    n: int | None = Field(default=None, ge=1)
    period: TimeRange | None = None


class OrderBy(StrictModel):
    field: str = Field(min_length=1)
    direction: Literal["asc", "desc"]


class OutputSpec(StrictModel):
    mode: Literal["detail", "aggregate", "summary"]
    format: Literal["table", "text", "chart"]
    include_details: bool
    include_explanation: bool


class Ambiguity(StrictModel):
    term: str = Field(min_length=1)
    type: Literal[
        "time", "metric", "dimension", "business_rule", "entity", "concept", "other"
    ]
    reason: str | None = None
    question: str | None = None
    candidates: list[Any] = Field(default_factory=list)


class Assumption(StrictModel):
    description: str = Field(min_length=1)
    source: str | None = None
    review_required: bool = False


class Confidence(StrictModel):
    overall: float = Field(ge=0, le=1)
    intent: float | None = Field(default=None, ge=0, le=1)
    metrics: float | None = Field(default=None, ge=0, le=1)
    dimensions: float | None = Field(default=None, ge=0, le=1)
    entities: float | None = Field(default=None, ge=0, le=1)
    time: float | None = Field(default=None, ge=0, le=1)
    filters: float | None = Field(default=None, ge=0, le=1)


class PlanContext(StrictModel):
    parent_plan_id: str | None = None
    operation: Literal["new", "modify", "refine", "compare"]


class QueryPlan(StrictModel):
    version: Literal["1.0"]
    status: Literal["ready", "needs_clarification", "invalid"]
    intent: Literal[
        "customer_selection", "metric_query", "group_analysis", "trend_analysis",
        "ranking", "entity_lookup", "customer_profile", "segment_analysis", "comparison",
    ]
    subject: Literal["customer", "product", "branch", "transaction", "holding"]
    metrics: list[str]
    dimensions: list[str]
    filters: list[FilterNode]
    entities: list[EntityRef]
    time_range: TimeRange | None
    group_by: list[str]
    having: list[FilterNode]
    order_by: list[OrderBy]
    limit: int | None = Field(default=None, ge=1)
    output: OutputSpec
    ambiguities: list[Ambiguity]
    assumptions: list[Assumption]
    confidence: Confidence
    context: PlanContext

    @model_validator(mode="after")
    def validate_status_contract(self) -> "QueryPlan":
        if self.status == "needs_clarification" and not self.ambiguities:
            raise ValueError("needs_clarification requires ambiguities")
        if self.intent == "ranking" and not self.order_by:
            raise ValueError("ranking requires order_by")
        if self.intent == "trend_analysis" and self.time_range is None:
            raise ValueError("trend_analysis requires time_range")
        return self

