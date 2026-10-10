from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class StructuredLLMProvider(ABC):
    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Return a validated structured object or raise an explicit error."""

