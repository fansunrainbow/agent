from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


POLICY_DIR = Path(__file__).resolve().parent / "policies"


def load_policy(name: str) -> dict[str, Any]:
    with (POLICY_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
