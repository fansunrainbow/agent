from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import yaml

from marketing.opportunity_detector import OpportunityDetector
from marketing.rule_registry import RULE_DIR, RuleConfigurationError, RuleRegistry
from marketing.segment_engine import SegmentEngine
from marketing.services import CustomerProfileService
from marketing.tag_engine import TagEngine


def copy_rules(target: Path):
    target.mkdir(exist_ok=True)
    for source in RULE_DIR.glob("*.yaml"):
        shutil.copyfile(source, target / source.name)


def append_rule(path: Path, top: str, rule_id: str, rule: dict):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data[top][rule_id] = rule
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def common_rule(name, condition):
    return {"name": name, "version": "1.0", "effective_from": "2026-01-01", "source": "user_defined", "defaults": {"threshold": 0.2}, "condition": condition}


def test_new_tag_segment_opportunity_require_only_yaml(tmp_path, customer_factory):
    copy_rules(tmp_path)
    append_rule(tmp_path / "tag_rules.yaml", "tags", "bond_low", common_rule("债券低配置", {"feature": "bond_holding_ratio", "operator": "lt", "parameter": "threshold"}))
    append_rule(tmp_path / "segment_rules.yaml", "segments", "bond_low_segment", common_rule("债券低配置客群", {"feature": "bond_holding_ratio", "operator": "lt", "parameter": "threshold"}))
    opportunity = common_rule("债券配置沟通机会", {"feature": "bond_holding_ratio", "operator": "lt", "parameter": "threshold"})
    opportunity.update({"priority": "medium", "evidence": ["bond_holding_ratio"], "explanation_template": "债券配置低于规则阈值。"})
    append_rule(tmp_path / "opportunity_rules.yaml", "opportunities", "bond_allocation_opportunity", opportunity)
    registry = RuleRegistry(tmp_path)
    customer = customer_factory()
    assert any(item.tag_id == "bond_low" for item in TagEngine(registry).calculate(customer))
    assert SegmentEngine(registry).evaluate("bond_low_segment", [customer]).matched_customer_ids == ["c1"]
    assert any(item.opportunity_id == "bond_allocation_opportunity" for item in OpportunityDetector(registry).find(customer))


def test_unregistered_rule_feature_is_rejected(tmp_path):
    copy_rules(tmp_path)
    append_rule(tmp_path / "tag_rules.yaml", "tags", "invented", common_rule("虚构", {"feature": "risk_preference", "operator": "eq", "value": "aggressive"}))
    with pytest.raises(RuleConfigurationError, match="unregistered feature"):
        RuleRegistry(tmp_path).load("tag")


@pytest.mark.parametrize("attribute", ["risk_preference", "purchase_intent", "churn_probability", "income_level", "marital_status", "customer_satisfaction"])
def test_unsupported_customer_attributes_are_never_inferred(customer_factory, attribute):
    result = CustomerProfileService().get_attribute(customer_factory(), attribute)
    assert result["supported"] is False
    assert result["code"] == "UNSUPPORTED_CUSTOMER_ATTRIBUTE"
    assert not any(word in str(result) for word in ("保守", "稳健", "激进", "高概率"))
