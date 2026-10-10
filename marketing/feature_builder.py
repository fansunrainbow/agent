from __future__ import annotations

from typing import Any

from guardrail.catalog import MetadataCatalog
from guardrail.execution_manager import ExecutionResult
from guardrail.models import SQLArtifact

from .models import CustomerFeature, FeatureValue


class FeatureBuildError(ValueError):
    def __init__(self, code: str, message: str, evidence: Any | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence


class CustomerFeatureBuilder:
    """Builds traceable customer features exclusively from a successful Stage 6 result."""

    def __init__(self, catalog: MetadataCatalog | None = None):
        self.catalog = catalog or MetadataCatalog()

    def build(
        self,
        result: ExecutionResult,
        artifact: SQLArtifact,
        *,
        feature_time_ranges: dict[str, dict[str, Any]] | None = None,
        missing_states: dict[tuple[str, str], str] | None = None,
    ) -> list[CustomerFeature]:
        self._validate_safe_result(result, artifact)
        columns = result.columns or artifact.selected_columns
        if "pty_id" not in columns:
            raise FeatureBuildError("CUSTOMER_GRAIN_REQUIRED", "Customer Feature 必须来自包含 pty_id 的客户粒度安全结果。")
        allowed = set(self.catalog.metrics) | set(self.catalog.dimensions) | {"pty_id"}
        unsupported = sorted(set(columns) - allowed)
        if unsupported:
            raise FeatureBuildError("UNREGISTERED_FEATURE", "安全结果包含未注册 Feature。", unsupported)
        time_ranges = feature_time_ranges or {}
        missing_overrides = missing_states or {}
        plan_range = artifact.query_plan.get("time_range")
        snapshot = self.catalog.tables.get("ads_cust_info_d", {}).get("time", {}).get("max")
        records = self._records(result.rows, columns)
        built: list[CustomerFeature] = []
        for record in records:
            customer_id = record.get("pty_id")
            if customer_id is None:
                raise FeatureBuildError("CUSTOMER_ID_MISSING", "安全结果中存在空客户标识。")
            values: dict[str, FeatureValue] = {}
            source_metrics: list[str] = []
            source_dimensions: list[str] = []
            for feature_id in columns:
                if feature_id == "pty_id":
                    continue
                kind = "metric" if feature_id in self.catalog.metrics else "dimension"
                value = record.get(feature_id)
                missing_state = missing_overrides.get((str(customer_id), feature_id)) or self._missing_state(value, kind)
                feature_range = time_ranges.get(feature_id, plan_range if kind == "metric" else None)
                values[feature_id] = FeatureValue(
                    feature_id=feature_id, kind=kind, value=value, time_range=feature_range,
                    source="stage6_safe_result", confidence=1.0, missing_state=missing_state,
                )
                (source_metrics if kind == "metric" else source_dimensions).append(feature_id)
            built.append(CustomerFeature(
                customer_id=str(customer_id), features=values,
                source_metrics=source_metrics, source_dimensions=source_dimensions,
                attribute_snapshot_date=snapshot, metric_time_range=plan_range, confidence=1.0,
                trace=[{
                    "stage": "feature_builder", "query_id": artifact.query_id,
                    "safe_result_status": result.status, "guardrail_allowed": True,
                    "source_columns": columns,
                }],
            ))
        return built

    @staticmethod
    def _missing_state(value: Any, kind: str) -> str:
        if value is None:
            return "no_record" if kind == "metric" else "unknown"
        if kind == "metric" and isinstance(value, (int, float)) and value == 0:
            return "zero"
        return "observed"

    @staticmethod
    def _records(rows: list[Any], columns: list[str]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            elif hasattr(row, "_mapping"):
                result.append(dict(row._mapping))
            else:
                result.append(dict(zip(columns, row)))
        return result

    @staticmethod
    def _validate_safe_result(result: ExecutionResult, artifact: SQLArtifact) -> None:
        if result.status != "success" or result.trace is None:
            raise FeatureBuildError("UNSAFE_RESULT", "仅接受 Stage 6 status=success 的结果。")
        if not result.trace.validation.get("allowed"):
            raise FeatureBuildError("GUARDRAIL_NOT_PASSED", "Stage 6 Guardrail 未通过。")
        result_validation = result.trace.result_validation or {}
        if not result_validation.get("allowed"):
            raise FeatureBuildError("RESULT_VALIDATION_NOT_PASSED", "Stage 6 Result Validator 未通过。")
        if result.trace.query_id != artifact.query_id:
            raise FeatureBuildError("TRACE_ARTIFACT_MISMATCH", "Execution Trace 与 SQL Artifact 不属于同一查询。")
