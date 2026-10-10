from __future__ import annotations

from copy import deepcopy
from typing import Any, TypeVar

from pydantic import BaseModel

from .base import StructuredLLMProvider


T = TypeVar("T", bound=BaseModel)


class UnavailableProvider(StructuredLLMProvider):
    def generate_structured(self, **_: Any) -> T:
        raise RuntimeError("未配置 LLM Provider；未伪造在线调用结果。")


class StaticStructuredProvider(StructuredLLMProvider):
    """Deterministic test provider that returns one preconfigured payload."""

    def __init__(self, response: dict[str, Any]):
        self.response = deepcopy(response)

    def generate_structured(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        return response_model.model_validate(deepcopy(self.response))

