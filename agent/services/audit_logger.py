from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from agent.models import AgentState


class JsonlAuditLogger:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def _redact(text: str) -> str:
        text = re.sub(r"C\d{15}", "[CUSTOMER_ID]", text)
        text = re.sub(r"(?<!\d)\d{16,19}(?!\d)", "[LONG_ID]", text)
        return text

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls._redact(value)
        if isinstance(value, list):
            return [cls._redact_value(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._redact_value(item) for key, item in value.items()}
        return value

    def write(self, state: AgentState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = self._redact_value(state.model_dump(mode="json"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
