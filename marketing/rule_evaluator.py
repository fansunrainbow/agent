from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import CustomerFeature, RuleEvidence


@dataclass
class Evaluation:
    passed: bool | None
    status: str
    evidence: list[RuleEvidence]
    parameters: dict[str, Any]
    threshold_sources: dict[str, str]
    warnings: list[dict[str, Any]] = field(default_factory=list)


class RuleEvaluator:
    """Generic three-valued Boolean evaluator shared by tags, segments and opportunities."""

    def evaluate(
        self,
        feature: CustomerFeature,
        rule: dict[str, Any],
        user_parameters: dict[str, Any] | None = None,
        business_parameters: dict[str, Any] | None = None,
    ) -> Evaluation:
        parameters, sources = self._parameters(rule, user_parameters or {}, business_parameters or {})
        evidence: list[RuleEvidence] = []
        warnings: list[dict[str, Any]] = []
        node = rule.get("condition") or {"logic": rule.get("logic", "AND"), "conditions": rule.get("conditions", [])}
        passed = self._node(node, feature, parameters, sources, evidence, warnings)
        observed_ranges = {
            self._freeze(item.time_range) for item in evidence
            if item.feature_kind == "metric" and item.passed is not None and item.time_range is not None
        }
        if len(observed_ranges) > 1:
            warnings.append({
                "code": "METRIC_TIME_RANGE_CONFLICT",
                "message": "规则组合了不同统计时间范围的指标，已拒绝判断。",
                "ranges": [dict(item) for item in observed_ranges],
            })
            passed = None
            status = "time_conflict"
        elif passed is None:
            status = "insufficient_data"
        else:
            status = "matched" if passed else "not_matched"
        return Evaluation(passed, status, evidence, parameters, sources, warnings)

    @staticmethod
    def _freeze(value: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(sorted(value.items()))

    @staticmethod
    def _parameters(rule: dict[str, Any], user: dict[str, Any], business: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        defaults = rule.get("defaults", {}) or {}
        keys = set(defaults) | set(business) | set(user)
        values: dict[str, Any] = {}
        sources: dict[str, str] = {}
        for key in keys:
            if key in user:
                values[key], sources[key] = user[key], "user_input"
            elif key in business:
                values[key], sources[key] = business[key], "business_config"
            else:
                values[key], sources[key] = defaults[key], "default"
        return values, sources

    def _node(
        self,
        node: dict[str, Any],
        feature: CustomerFeature,
        parameters: dict[str, Any],
        sources: dict[str, str],
        evidence: list[RuleEvidence],
        warnings: list[dict[str, Any]],
    ) -> bool | None:
        if "logic" in node:
            logic = str(node["logic"]).upper()
            values = [self._node(child, feature, parameters, sources, evidence, warnings) for child in node.get("conditions", [])]
            if logic == "AND":
                return False if False in values else (None if None in values else True)
            if logic == "OR":
                return True if True in values else (None if None in values else False)
            value = values[0]
            return None if value is None else not value

        feature_id = node["feature"]
        item = feature.get(feature_id)
        operator = node["operator"]
        parameter = node.get("parameter")
        if parameter:
            if parameter not in parameters:
                raise ValueError(f"missing rule parameter: {parameter}")
            threshold, threshold_source = parameters[parameter], sources[parameter]
        else:
            threshold, threshold_source = node.get("value"), "rule_value"
        passed: bool | None
        if item is None:
            passed = None
            actual, source, time_range, missing_state, kind = None, "unavailable", None, "unknown", "unknown"
            warnings.append({"code": "FEATURE_NOT_AVAILABLE", "feature_id": feature_id})
        else:
            actual, source, time_range, missing_state, kind = item.value, item.source, item.time_range, item.missing_state, item.kind
            passed = self._compare(actual, operator, threshold, missing_state)
            if passed is None:
                warnings.append({"code": "FEATURE_VALUE_UNAVAILABLE", "feature_id": feature_id, "missing_state": missing_state})
        evidence.append(RuleEvidence(
            feature_id=feature_id, feature_kind=kind, actual_value=actual, operator=operator,
            threshold=threshold, passed=passed, source=source, threshold_source=threshold_source,
            time_range=time_range, missing_state=missing_state,
        ))
        return passed

    @staticmethod
    def _compare(actual: Any, operator: str, threshold: Any, missing_state: str) -> bool | None:
        if operator == "exists":
            return True if missing_state in {"observed", "zero"} else (False if missing_state == "no_record" else None)
        if operator == "not_exists":
            return True if missing_state == "no_record" else (False if missing_state in {"observed", "zero"} else None)
        if missing_state not in {"observed", "zero"}:
            return None
        try:
            return {
                "eq": lambda: actual == threshold,
                "neq": lambda: actual != threshold,
                "gt": lambda: actual > threshold,
                "gte": lambda: actual >= threshold,
                "lt": lambda: actual < threshold,
                "lte": lambda: actual <= threshold,
                "in": lambda: actual in threshold,
                "not_in": lambda: actual not in threshold,
                "between": lambda: threshold[0] <= actual <= threshold[1],
            }[operator]()
        except (KeyError, TypeError, ValueError, IndexError):
            return None
