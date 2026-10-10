from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any

from .models import SQLArtifact


class ResultNormalizer:
    """Convert DB-driver rows into stable, JSON-safe business records."""

    @classmethod
    def value(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            integral = value.to_integral_value()
            return int(integral) if value == integral else float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls.value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.value(item) for item in value]
        return value

    @classmethod
    def normalize(cls, rows: list[Any], columns: list[str], artifact: SQLArtifact) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                record = row
            elif hasattr(row, "_mapping"):
                record = dict(row._mapping)
            else:
                record = dict(zip(columns, row))
            records.append({str(key): cls.value(value) for key, value in record.items()})
        intent = artifact.query_plan.get("intent")
        if intent == "trend_analysis":
            bucket = next((key for key in ("date", "month", "quarter", "period") if key in columns), None)
            if bucket:
                records.sort(key=lambda item: (item.get(bucket) is None, str(item.get(bucket))))
        elif intent in {"group_analysis", "segment_analysis"}:
            groups = artifact.query_plan.get("group_by", [])
            records.sort(key=lambda item: tuple(str(item.get(key)) for key in groups))
        elif intent in {"customer_selection", "entity_lookup"} and not artifact.query_plan.get("order_by"):
            records.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
        return records
