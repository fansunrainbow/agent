from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    question: str = Field(min_length=1)
    term: str | None = None
    options: list[Any] = Field(default_factory=list)
    path: str | None = None


class ClarificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needed: bool
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    unsupported: bool = False
    message: str | None = None

