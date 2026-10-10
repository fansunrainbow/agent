from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from guardrail.execution_manager import ExecutionResult, ExecutionTrace
from guardrail.models import SQLArtifact
from marketing.feature_builder import CustomerFeatureBuilder
from marketing.segment_engine import SegmentEngine
from marketing.services import CohortAnalysisService, MarketingAnalysisService
from marketing.strategy_engine import StrategyEngine


def load_stage6_export(path: Path) -> tuple[ExecutionResult, SQLArtifact]:
    data = json.loads(path.read_text(encoding="utf-8"))
    artifact = SQLArtifact(**data["artifact"])
    result_data = data["execution_result"]
    trace = ExecutionTrace(**result_data["trace"])
    result = ExecutionResult(result_data["status"], result_data["rows"], result_data["columns"], trace)
    return result, artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 7 marketing acceptance CLI (consumes exported Stage 6 safe results)")
    parser.add_argument("--input", required=True, type=Path, help="Stage 6 result export JSON")
    parser.add_argument("--customer-id", help="Only output one customer")
    parser.add_argument("--segment", default="high_asset_low_fund", help="Configured segment rule id")
    parser.add_argument("--attribute", help="Audit whether an attribute is supported")
    parser.add_argument("--specific-product", help="Test the suitability guard for a concrete product request")
    parser.add_argument("--allow-demo-fixture", action="store_true", help="Explicitly allow the bundled synthetic acceptance fixture")
    args = parser.parse_args()

    result, artifact = load_stage6_export(args.input)
    is_fixture = bool((result.trace.validation if result.trace else {}).get("fixture"))
    if is_fixture and not args.allow_demo_fixture:
        raise SystemExit("Refusing synthetic fixture without --allow-demo-fixture; production input must come from Stage 6 ExecutionManager.")
    features = CustomerFeatureBuilder().build(result, artifact)
    if args.customer_id:
        features = [item for item in features if item.customer_id == args.customer_id]
    analysis = MarketingAnalysisService()
    segment = SegmentEngine().evaluate(args.segment, features)
    output = {
        "customers": [analysis.analyze_customer(item) for item in features],
        "segment": segment.to_dict(),
        "cohort_analysis": CohortAnalysisService().analyze(segment, features),
    }
    if args.attribute:
        output["attribute_check"] = [analysis.profiles.get_attribute(item, args.attribute) for item in features]
    if args.specific_product:
        output["specific_product_request"] = StrategyEngine().request_specific_product_recommendation(args.specific_product)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
