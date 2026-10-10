from __future__ import annotations

from copy import deepcopy
import inspect

from agent import AgentOrchestrator
from agent.models import AgentState, GroundedCondition
from agent.services.concept_expander import ConceptExpander
from guardrail.sql_generator import SQLGenerator
from scripts.validate_query_plan import validate_plan_data


def _filter(plan: dict, target: str) -> dict:
    return next(item for item in plan["filters"] if item.get("target") == target)


def test_stock_product_expands_to_product_category_filter():
    state = AgentOrchestrator().run("2026年Q1股票产品交易额是多少？")
    assert state.status == "ready"
    item = _filter(state.query_plan, "product_primary_category")
    assert (item["type"], item["operator"], item["value"]) == ("dimension", "eq", "stock")
    assert not any(node.get("type") == "concept" for node in state.query_plan["filters"])


def test_fund_product_uses_same_registry_driven_expansion():
    state = AgentOrchestrator().run("查询基金类产品")
    assert state.status == "ready"
    assert _filter(state.query_plan, "product_primary_category")["value"] == "fund"


def test_bond_product_uses_real_name_canonical_value():
    state = AgentOrchestrator().run("查询债券产品")
    assert state.status == "ready"
    assert _filter(state.query_plan, "product_primary_category")["value"] == "bond"


def test_unregistered_category_concept_is_unsupported():
    expander = ConceptExpander()
    expander.expansions["unknown_category"] = {
        **deepcopy(expander.expansions["stock_product"]),
        "concept_id": "unknown_category",
    }
    state = AgentState(user_query="未知类别")
    state.grounded_conditions = [GroundedCondition(
        condition_id="c1", original_surface="未知类别", semantic_type="concept",
        target="unknown_category", operator="eq", value=True,
        source="test", confidence=1.0,
    )]
    expander.expand(state)
    assert state.grounded_conditions[0].status == "unsupported"
    assert "Business Dictionary" in state.grounded_conditions[0].reason


def test_stock_category_does_not_enter_product_entity_resolver():
    state = AgentOrchestrator().run("查询持有股票类产品的客户")
    assert state.status == "ready"
    assert state.resolved_entities == []
    assert state.query_plan["entities"] == []


def test_concrete_product_still_enters_entity_resolver():
    state = AgentOrchestrator().run("贵州茅台持仓客户")
    assert state.status == "ready"
    assert state.resolved_entities[0]["entity_type"] == "product"
    assert _filter(state.query_plan, "held_product")["value"] == "9900269727"


def test_holding_stock_category_compiles_as_scoped_exists():
    state = AgentOrchestrator().run("查询持有股票类产品的客户")
    relation = _filter(state.query_plan, "held_product")
    assert relation["operator"] == "exists" and relation.get("value") is None
    artifact = SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)
    assert "EXISTS (SELECT" in artifact.sql
    assert "IN (SELECT DISTINCT" in artifact.sql
    assert "FROM dim_product" in artifact.sql
    assert "up_prdt_type_name = :" in artifact.sql


def test_no_holding_stock_category_compiles_as_scoped_not_exists():
    state = AgentOrchestrator().run("没有持有股票类产品的客户")
    relation = _filter(state.query_plan, "held_product")
    assert relation["operator"] == "not_exists" and relation.get("value") is None
    artifact = SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)
    assert "NOT EXISTS (SELECT" in artifact.sql
    assert "up_prdt_type_name = :" in artifact.sql
    assert "up_prdt_type_name <>" not in artifact.sql


def test_invalid_canonical_category_is_rejected_by_stage4_validator():
    state = AgentOrchestrator().run("2026年Q1股票产品交易额是多少？")
    plan = deepcopy(state.query_plan)
    _filter(plan, "product_primary_category")["value"] = "SYNTHETIC_STOCK_ID"
    validation = validate_plan_data(plan)
    assert not validation["valid"]
    assert "INVALID_DIMENSION_VALUE" in {item["code"] for item in validation["errors"]}


def test_expansion_provenance_is_retained_in_trace():
    state = AgentOrchestrator().run("2026年Q1股票产品交易额是多少？")
    trace = next(item for item in state.trace if item.step == "expand_concepts")
    record = trace.output_summary[0]
    assert record["concept_id"] == "stock_product"
    assert record["target_dimension"] == "product_primary_category"
    assert record["source"] == "metadata/concept_expansions.yaml"


def test_expanded_plan_passes_stage4_structural_and_semantic_validation():
    state = AgentOrchestrator().run("2026年Q1股票产品交易额是多少？")
    validation = validate_plan_data(state.query_plan)
    assert validation["valid"], validation["errors"]


def test_expansion_implementation_has_no_smoke_or_stock_special_branch():
    source = inspect.getsource(ConceptExpander)
    assert "SMOKE_07" not in source
    assert "stock_product" not in source


def test_sql_compiler_still_rejects_unexpanded_raw_concept():
    state = AgentOrchestrator().run("2026年Q1股票产品交易额是多少？")
    plan = deepcopy(state.query_plan)
    plan["filters"] = [{
        "id": "f1", "type": "concept", "target": "stock_product", "operator": "eq",
        "value": True, "source": "dictionary", "confidence": 1.0,
    }]
    validation = validate_plan_data(plan)
    assert validation["valid"]
    try:
        SQLGenerator().generate("raw-concept", plan, validation)
    except Exception as exc:
        assert getattr(exc, "code", None) == "SQL_UNSUPPORTED_COMBINATION"
    else:
        raise AssertionError("raw concept must remain rejected by SQL compiler")
