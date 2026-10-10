from copy import deepcopy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from normalize_query_plan import normalize_query_plan
from tests.test_query_plan_validator import base_plan


class QueryPlanNormalizerTests(unittest.TestCase):
    def test_operator_city_metric_and_quarter_are_canonicalized(self):
        plan = base_plan()
        plan["metrics"] = ["日均资产"]
        plan["time_range"] = {"type": "quarter", "year": 2026, "quarter": "Q1"}
        plan["filters"] = [{
            "id": "f1", "type": "dimension", "target": "city",
            "operator": "大于", "value": "南京市", "source": "explicit", "confidence": 1.0,
        }]

        normalized = normalize_query_plan(plan)

        self.assertEqual(normalized["metrics"], ["average_total_asset"])
        self.assertEqual(normalized["time_range"]["quarter"], 1)
        self.assertEqual(normalized["filters"][0]["operator"], "gt")
        self.assertEqual(normalized["filters"][0]["value"], "南京")

    def test_unknown_semantics_are_not_guessed(self):
        plan = base_plan()
        plan["metrics"] = ["模型凭空猜测指标"]
        original = deepcopy(plan)

        normalized = normalize_query_plan(plan)

        self.assertEqual(normalized["metrics"], original["metrics"])


if __name__ == "__main__":
    unittest.main()
