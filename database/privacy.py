from __future__ import annotations

from typing import Any


SENSITIVE_MARKERS = ("name", "mobile", "phone", "contact", "id_card", "identity", "address", "email")
SAFE_IDENTIFIERS = {"pty_id", "customer_id", "product_name", "branch_name", "city", "province"}


def mask_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= 1:
        return "*"
    if len(text) == 2:
        return text[0] + "*"
    return text[0] + "*" * min(4, len(text) - 2) + text[-1]


def safe_records(rows: list[Any], columns: list[str]) -> list[dict[str, Any]]:
    records = []
    for row in rows:
        record = dict(row._mapping) if hasattr(row, "_mapping") else dict(row) if isinstance(row, dict) else dict(zip(columns, row))
        records.append({
            key: mask_value(value) if key.lower() not in SAFE_IDENTIFIERS and any(marker in key.lower() for marker in SENSITIVE_MARKERS) else value
            for key, value in record.items()
        })
    return records
