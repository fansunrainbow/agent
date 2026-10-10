from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.normalize_query_plan import normalize_query_plan


class RepairEngine:
    """Apply deterministic canonicalization only; never invent business semantics."""

    MAX_ATTEMPTS = 2
    REPAIRABLE_CODES = {
        "STRUCTURAL_ERROR",
        "UNKNOWN_OPERATOR",
        "INVALID_FILTER",
        "INVALID_TIME_RANGE",
        "INVALID_LIMIT",
    }

    @classmethod
    def is_repairable(cls, validation: dict[str, Any]) -> bool:
        errors = validation.get("errors", [])
        return bool(errors) and all(error.get("code") in cls.REPAIRABLE_CODES for error in errors)

    def repair(self, plan: dict[str, Any], validation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        before = deepcopy(plan)
        after = normalize_query_plan(before)
        return after, {
            "changed": after != plan,
            "error_codes": [item.get("code") for item in validation.get("errors", [])],
            "strategy": "registry_backed_canonical_normalization",
        }
