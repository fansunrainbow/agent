from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from marketing.rule_registry import RuleRegistry


SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "rule_snapshots.json"


def _hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check_rule_snapshot(path: Path = SNAPSHOT) -> dict[str, Any]:
    expected = json.loads(path.read_text(encoding="utf-8"))
    registry = RuleRegistry()
    actual = {kind: {rule_id: _hash(rule) for rule_id, rule in registry.load(kind).items()} for kind in ("tag", "segment", "opportunity", "strategy")}
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    for kind in sorted(set(expected) | set(actual)):
        old, new = expected.get(kind, {}), actual.get(kind, {})
        changed.extend(f"{kind}:{rule_id}" for rule_id in set(old) & set(new) if old[rule_id] != new[rule_id])
        added.extend(f"{kind}:{rule_id}" for rule_id in set(new) - set(old))
        removed.extend(f"{kind}:{rule_id}" for rule_id in set(old) - set(new))
    return {"passed": not (changed or added or removed), "changed": sorted(changed), "added": sorted(added), "removed": sorted(removed), "rule_count": sum(len(items) for items in actual.values())}
