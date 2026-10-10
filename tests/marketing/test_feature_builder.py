from __future__ import annotations

import pytest

from guardrail.execution_manager import ExecutionResult, ExecutionTrace
from guardrail.models import SQLArtifact
from marketing.feature_builder import CustomerFeatureBuilder, FeatureBuildError


def safe_fixture():
    plan = {"time_range": {"type": "quarter", "year": 2026, "quarter": 1}}
    artifact = SQLArtifact(
        "q1", "SELECT 1", {}, plan, metric_aliases=["average_total_asset", "trade_count"],
        selected_columns=["pty_id", "city", "average_total_asset", "trade_count"],
    )
    trace = ExecutionTrace(
        query_id="q1", query_plan=plan, status="success",
        validation={"allowed": True}, sql="SELECT 1", parameter_names=[], attempts=1,
        elapsed_ms=1.0, result_validation={"allowed": True},
    )
    result = ExecutionResult(
        "success", [("c1", "南京", 1_200_000, None), ("c2", "苏州", 0, 0)],
        ["pty_id", "city", "average_total_asset", "trade_count"], trace,
    )
    return result, artifact


def test_feature_builder_preserves_provenance_and_missing_states():
    result, artifact = safe_fixture()
    features = CustomerFeatureBuilder().build(result, artifact)
    assert features[0].get("average_total_asset").time_range == artifact.query_plan["time_range"]
    assert features[0].get("trade_count").missing_state == "no_record"
    assert features[1].get("average_total_asset").missing_state == "zero"
    assert features[0].get("city").kind == "dimension"
    assert features[0].trace[0]["guardrail_allowed"] is True


def test_feature_builder_rejects_non_safe_result():
    result, artifact = safe_fixture()
    result.status = "result_blocked"
    with pytest.raises(FeatureBuildError) as caught:
        CustomerFeatureBuilder().build(result, artifact)
    assert caught.value.code == "UNSAFE_RESULT"


def test_feature_builder_rejects_unregistered_feature():
    result, artifact = safe_fixture()
    result.columns.append("risk_preference")
    result.rows = [(*result.rows[0], "aggressive")]
    with pytest.raises(FeatureBuildError) as caught:
        CustomerFeatureBuilder().build(result, artifact)
    assert caught.value.code == "UNREGISTERED_FEATURE"
