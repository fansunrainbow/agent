from __future__ import annotations

from collections import Counter
from math import fsum
from typing import Any

from ..models import CustomerFeature, SegmentResult


class CohortAnalysisService:
    DISTRIBUTIONS = ["gender", "customer_level", "city", "branch"]
    ALLOCATION = ["cash_asset_ratio", "stock_holding_ratio", "fund_holding_ratio", "bond_holding_ratio", "wealth_management_holding_ratio"]

    def analyze(self, segment: SegmentResult, features: list[CustomerFeature]) -> dict[str, Any]:
        selected = [item for item in features if item.customer_id in set(segment.matched_customer_ids)]
        average_assets = self._numbers(selected, "average_total_asset")
        end_assets = self._numbers(selected, "period_end_asset")
        ages = self._numbers(selected, "age")
        trade_counts = self._numbers(selected, "trade_count")
        net_flows = self._numbers(selected, "net_inflow")
        distributions = {field: self._distribution(selected, field) for field in self.DISTRIBUTIONS}
        allocations = {field: self._mean(self._numbers(selected, field)) for field in self.ALLOCATION}
        return {
            "segment_id": segment.segment_id,
            "customer_count": len(selected),
            "asset_scale": fsum(end_assets) if end_assets else None,
            "average_asset": self._mean(average_assets),
            "average_age": self._mean(ages),
            "distributions": distributions,
            "allocation_structure": allocations,
            "trading_activity": {"average_trade_count": self._mean(trade_counts)},
            "fund_flow": {
                "total_net_inflow": fsum(net_flows) if net_flows else None,
                "net_inflow_customers": sum(1 for value in net_flows if value > 0),
                "net_outflow_customers": sum(1 for value in net_flows if value < 0),
            },
            "time_range": segment.time_range,
            "sources": {
                "metrics": ["period_end_asset", "average_total_asset", "trade_count", "net_inflow", *self.ALLOCATION],
                "dimensions": ["age", *self.DISTRIBUTIONS],
            },
            "missing_policy": "Only observed/zero values are aggregated; no_record and unknown are excluded and never coerced to zero.",
        }

    @staticmethod
    def _numbers(features: list[CustomerFeature], feature_id: str) -> list[float]:
        values = []
        for feature in features:
            item = feature.get(feature_id)
            if item and item.usable and isinstance(item.value, (int, float)):
                values.append(float(item.value))
        return values

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return fsum(values) / len(values) if values else None

    @staticmethod
    def _distribution(features: list[CustomerFeature], feature_id: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for feature in features:
            item = feature.get(feature_id)
            if item and item.usable:
                counter[str(item.value)] += 1
        return dict(sorted(counter.items()))
