from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolResult(BaseModel):
    """Uniform, serializable contract returned by every deterministic tool."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: Any = None
    source: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_failure_contract(self) -> "ToolResult":
        if not self.success and not self.error_code:
            raise ValueError("failed ToolResult requires error_code")
        return self

    @classmethod
    def ok(cls, data: Any, source: str, confidence: float = 1.0) -> "ToolResult":
        return cls(success=True, data=data, source=source, confidence=confidence)

    @classmethod
    def fail(cls, code: str, message: str, source: str, data: Any = None) -> "ToolResult":
        return cls(
            success=False,
            data=data,
            source=source,
            confidence=0.0,
            error_code=code,
            error_message=message,
        )

