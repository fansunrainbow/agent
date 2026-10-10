from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from guardrail.catalog import MetadataCatalog


RULE_DIR = Path(__file__).resolve().parent / "rules"


class RuleConfigurationError(ValueError):
    pass


class RuleRegistry:
    def __init__(self, rule_dir: Path = RULE_DIR, catalog: MetadataCatalog | None = None):
        self.rule_dir = rule_dir
        self.catalog = catalog or MetadataCatalog()

    def load(self, kind: str, as_of: date | None = None) -> dict[str, dict[str, Any]]:
        top = {"tag": "tags", "segment": "segments", "opportunity": "opportunities", "strategy": "strategies"}[kind]
        path = self.rule_dir / f"{kind}_rules.yaml"
        with path.open("r", encoding="utf-8") as handle:
            rules = (yaml.safe_load(handle) or {}).get(top, {})
        current = as_of or date.today()
        result: dict[str, dict[str, Any]] = {}
        for rule_id, raw in rules.items():
            rule = deepcopy(raw)
            rule["rule_id"] = rule_id
            self._validate_common(rule)
            if self._effective(rule, current):
                if kind != "strategy":
                    self._validate_condition_tree(rule.get("condition") or {"logic": rule.get("logic", "AND"), "conditions": rule.get("conditions", [])})
                result[rule_id] = rule
        return result

    @staticmethod
    def _validate_common(rule: dict[str, Any]) -> None:
        missing = [key for key in ("rule_id", "name", "version", "source", "effective_from") if not rule.get(key)]
        if missing:
            raise RuleConfigurationError(f"rule missing required fields: {missing}")
        if rule["source"] not in {"internal_config", "business_policy", "user_defined"}:
            raise RuleConfigurationError(f"unsupported rule source: {rule['source']}")

    @staticmethod
    def _effective(rule: dict[str, Any], current: date) -> bool:
        start = date.fromisoformat(str(rule["effective_from"]))
        end = date.fromisoformat(str(rule["effective_to"])) if rule.get("effective_to") else None
        return start <= current and (end is None or current <= end)

    def _validate_condition_tree(self, node: dict[str, Any]) -> None:
        if "logic" in node:
            logic = str(node["logic"]).upper()
            children = node.get("conditions", [])
            if logic not in {"AND", "OR", "NOT"} or not children or (logic == "NOT" and len(children) != 1):
                raise RuleConfigurationError(f"invalid boolean rule: {node}")
            for child in children:
                self._validate_condition_tree(child)
            return
        feature_id = node.get("feature")
        if feature_id not in self.catalog.metrics and feature_id not in self.catalog.dimensions:
            raise RuleConfigurationError(f"unregistered feature in rule: {feature_id}")
        if node.get("operator") not in {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "between", "exists", "not_exists"}:
            raise RuleConfigurationError(f"unsupported operator: {node.get('operator')}")
