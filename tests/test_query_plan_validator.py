import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from test_query_plan_cases import build_registries
from validate_query_plan import validate_plan


def base_plan():
    return {
        "version": "1.0",
        "status": "ready",
        "intent": "metric_query",
        "subject": "customer",
        "metrics": ["customer_count"],
        "dimensions": [],
        "filters": [],
        "entities": [],
        "time_range": None,
        "group_by": [],
        "having": [],
        "order_by": [],
        "limit": None,
        "output": {
            "mode": "aggregate",
            "format": "table",
            "include_details": False,
            "include_explanation": True,
        },
        "ambiguities": [],
        "assumptions": [],
        "confidence": {
            "overall": 1.0,
            "intent": 1.0,
            "metrics": 1.0,
            "dimensions": 1.0,
            "entities": 1.0,
            "time": 1.0,
            "filters": 1.0,
        },
        "context": {"parent_plan_id": None, "operation": "new"},
    }


class QueryPlanFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registries = build_registries()

    def validate(self, plan):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            return validate_plan(path, self.registries)

    def assert_error(self, plan, code):
        result = self.validate(plan)
        self.assertFalse(result["valid"], result)
        self.assertIn(code, {item["code"] for item in result["errors"]}, result)

    def test_unknown_intent(self):
        plan = base_plan()
        plan["intent"] = "invented_analysis"
        self.assert_error(plan, "UNKNOWN_INTENT")

    def test_metric_required_time(self):
        plan = base_plan()
        plan["metrics"] = ["average_total_asset"]
        self.assert_error(plan, "MISSING_REQUIRED_TIME_RANGE")

    def test_reversed_date_range(self):
        plan = base_plan()
        plan["time_range"] = {
            "type": "date_range", "start": "2026-04-01", "end": "2026-03-01"
        }
        self.assert_error(plan, "INVALID_TIME_RANGE")

    def test_metric_dimension_without_safe_path(self):
        plan = base_plan()
        plan["metrics"] = ["total_asset"]
        plan["dimensions"] = ["product"]
        self.assert_error(plan, "UNSUPPORTED_COMBINATION")

    def test_intent_capability_is_enforced(self):
        plan = base_plan()
        plan["intent"] = "customer_profile"
        plan["metrics"] = []
        plan["group_by"] = ["city"]
        plan["entities"] = [{
            "entity_type": "customer",
            "surface": "C1",
            "resolution_status": "resolved",
            "resolved": {"id": "C1", "name": "C1", "entity_type": "customer", "attributes": {}},
            "confidence": 1.0,
            "source": "exact_match",
        }]
        self.assert_error(plan, "UNSUPPORTED_CAPABILITY")

    def test_operator_value_shape(self):
        plan = base_plan()
        plan["filters"] = [{
            "id": "f1", "type": "dimension", "target": "age",
            "operator": "between", "value": [18], "source": "explicit", "confidence": 1.0,
        }]
        self.assert_error(plan, "INVALID_FILTER")

    def test_entity_filter_must_reference_resolved_entity(self):
        plan = base_plan()
        plan["intent"] = "customer_selection"
        plan["metrics"] = []
        plan["filters"] = [{
            "id": "f1", "type": "entity", "target": "held_product",
            "operator": "exists", "value": "P2", "source": "entity_resolution", "confidence": 1.0,
        }]
        plan["entities"] = [{
            "entity_type": "product",
            "surface": "产品一",
            "resolution_status": "resolved",
            "resolved": {"id": "P1", "name": "产品一", "entity_type": "product", "attributes": {}},
            "confidence": 1.0,
            "source": "exact_match",
        }]
        self.assert_error(plan, "UNRESOLVED_ENTITY")

    def test_assumption_requires_source_and_review(self):
        plan = base_plan()
        plan["assumptions"] = [{"description": "默认使用当前机构归属"}]
        self.assert_error(plan, "UNDECLARED_ASSUMPTION")

    def test_ready_requires_execute_confidence(self):
        plan = base_plan()
        plan["confidence"]["overall"] = 0.80
        self.assert_error(plan, "LOW_CONFIDENCE")

    def test_invalid_limit(self):
        plan = base_plan()
        plan["limit"] = 0
        self.assert_error(plan, "INVALID_LIMIT")


if __name__ == "__main__":
    unittest.main()
