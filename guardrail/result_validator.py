from __future__ import annotations

import math
from typing import Any, Iterable

from .catalog import MetadataCatalog
from .models import GuardIssue, GuardResult, SQLArtifact
from .policy import load_policy


class ResultValidator:
    def __init__(self, catalog: MetadataCatalog | None = None) -> None:
        self.catalog = catalog or MetadataCatalog()
        self.policy = load_policy("result_policy.yaml")

    def check(self, rows: Iterable[Any], artifact: SQLArtifact, columns: list[str] | None = None) -> GuardResult:
        materialized = list(rows)
        issues: list[GuardIssue] = []
        if not materialized:
            issues.append(GuardIssue("EMPTY_RESULT", "查询结果为空；SQL 可执行，但需确认筛选条件是否符合预期。", "warning"))
        maximum = int(self.policy["max_result_rows"])
        if len(materialized) > maximum:
            issues.append(GuardIssue("RESULT_ROW_LIMIT_EXCEEDED", "实际结果行数超过安全上限。", evidence=len(materialized)))
        records = self._records(materialized, columns or artifact.selected_columns)
        ratio_metrics = {metric for metric in artifact.metric_aliases if metric.endswith("_ratio") or "rate" in metric}
        for row_index, record in enumerate(records):
            for field, value in record.items():
                if isinstance(value, float) and not math.isfinite(value):
                    issues.append(GuardIssue("NON_FINITE_RESULT", f"结果 {field} 出现 NaN/Infinity。", path=f"rows[{row_index}].{field}"))
                if field == "customer_count" and isinstance(value, (int, float)):
                    if not math.isfinite(value) or value < 0 or int(value) != value:
                        issues.append(GuardIssue("INVALID_COUNT_RESULT", "客户数必须是非负整数。", path=f"rows[{row_index}].{field}", evidence=value))
                if field in ratio_metrics and isinstance(value, (int, float)):
                    if not float(self.policy["ratio_min"]) <= value <= float(self.policy["ratio_max"]):
                        issues.append(GuardIssue("RATIO_OUT_OF_RANGE", f"比例指标 {field} 超出 [0,1]。", path=f"rows[{row_index}].{field}", evidence=value))
        keys = [record.get("pty_id") for record in records if record.get("pty_id") is not None]
        if keys:
            amplification = len(keys) / max(1, len(set(keys)))
            if amplification > float(self.policy["duplicate_amplification_threshold"]):
                issues.append(GuardIssue("DUPLICATE_AMPLIFICATION", "客户主键重复，可能发生 Join 放大。", evidence={"ratio": amplification, "rows": len(keys), "distinct": len(set(keys))}))
        return GuardResult("result", not any(item.severity == "block" for item in issues), issues, {"row_count": len(materialized)})

    @staticmethod
    def _records(rows: list[Any], columns: list[str]) -> list[dict[str, Any]]:
        records = []
        for row in rows:
            if isinstance(row, dict):
                records.append(row)
            elif hasattr(row, "_mapping"):
                records.append(dict(row._mapping))
            else:
                records.append(dict(zip(columns, row)))
        return records
