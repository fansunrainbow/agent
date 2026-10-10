from __future__ import annotations

from typing import Any

from guardrail.catalog import MetadataCatalog

from ..models import CustomerFeature, CustomerTag


class CustomerProfileService:
    SECTIONS = {
        "basic_profile": ["age", "gender", "customer_level", "customer_status", "customer_type", "city", "province", "branch", "parent_branch"],
        "asset_profile": ["average_total_asset", "period_end_asset", "asset_change", "asset_change_rate", "cash_asset"],
        "holding_profile": ["holding_market_value", "stock_holding_value", "fund_holding_value", "bond_holding_value", "wealth_management_holding_value"],
        "trading_profile": ["trade_amount", "trade_count", "stock_trade_amount", "fund_trade_amount"],
        "fund_flow_profile": ["total_inflow", "total_outflow", "net_inflow"],
        "allocation_profile": ["cash_asset_ratio", "stock_holding_ratio", "fund_holding_ratio", "bond_holding_ratio", "wealth_management_holding_ratio"],
    }

    def __init__(self, catalog: MetadataCatalog | None = None):
        self.catalog = catalog or MetadataCatalog()

    def build_360(self, feature: CustomerFeature, tags: list[CustomerTag]) -> dict[str, Any]:
        profile: dict[str, Any] = {
            "customer_id": feature.customer_id,
            "attribute_snapshot_date": feature.attribute_snapshot_date,
            "metric_time_range": feature.metric_time_range,
            "confidence": feature.confidence,
        }
        for section, fields in self.SECTIONS.items():
            profile[section] = {
                field: feature.features[field].to_dict()
                for field in fields if field in feature.features
            }
        profile["tags"] = [tag.to_dict() for tag in tags if tag.matched]
        profile["trace"] = feature.trace
        return profile

    def get_attribute(self, feature: CustomerFeature, attribute_id: str) -> dict[str, Any]:
        if attribute_id not in self.catalog.metrics and attribute_id not in self.catalog.dimensions:
            return {
                "supported": False,
                "code": "UNSUPPORTED_CUSTOMER_ATTRIBUTE",
                "attribute_id": attribute_id,
                "message": "当前 Metric/Dimension Registry 没有该属性，系统不能据此推断客户画像。",
                "available_alternatives": sorted(feature.features),
            }
        item = feature.get(attribute_id)
        if item is None or not item.usable:
            return {
                "supported": False,
                "code": "ATTRIBUTE_DATA_UNAVAILABLE",
                "attribute_id": attribute_id,
                "message": "属性已注册，但当前安全结果没有可用记录。",
                "missing_state": item.missing_state if item else "unknown",
            }
        return {"supported": True, "attribute": item.to_dict()}
