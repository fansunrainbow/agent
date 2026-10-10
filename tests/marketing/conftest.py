from __future__ import annotations

from copy import deepcopy

import pytest

from marketing.models import CustomerFeature, FeatureValue


@pytest.fixture
def time_range():
    return {"type": "quarter", "year": 2026, "quarter": 1}


@pytest.fixture
def customer_factory(time_range):
    def build(customer_id="c1", values=None, missing=None, ranges=None):
        base = {
            "age": 42,
            "gender": "F",
            "customer_level": "1000001",
            "city": "南京",
            "average_total_asset": 1_850_000,
            "period_end_asset": 1_900_000,
            "asset_change": -100_000,
            "asset_change_rate": -0.05,
            "cash_asset": 800_000,
            "cash_asset_ratio": 0.43,
            "holding_market_value": 1_000_000,
            "stock_holding_ratio": 0.75,
            "fund_holding_ratio": 0.043,
            "bond_holding_ratio": 0.05,
            "wealth_management_holding_ratio": 0.02,
            "trade_amount": 300_000,
            "trade_count": 35,
            "stock_trade_amount": 250_000,
            "fund_trade_amount": 50_000,
            "total_inflow": 100_000,
            "total_outflow": 300_000,
            "net_inflow": -200_000,
        }
        base.update(values or {})
        dimensions = {"age", "gender", "customer_level", "city"}
        features = {}
        for feature_id, value in base.items():
            kind = "dimension" if feature_id in dimensions else "metric"
            state = (missing or {}).get(feature_id, "zero" if kind == "metric" and value == 0 else "observed")
            features[feature_id] = FeatureValue(
                feature_id, kind, value,
                (ranges or {}).get(feature_id, deepcopy(time_range)) if kind == "metric" else None,
                "stage6_safe_result", 1.0, state,
            )
        return CustomerFeature(
            customer_id, features,
            [key for key in features if key not in dimensions],
            [key for key in features if key in dimensions],
            "20260531", deepcopy(time_range), 1.0,
        )
    return build
