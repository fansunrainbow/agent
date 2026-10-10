from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from agent import AgentOrchestrator
from agent.tools import EntityTool
from guardrail.catalog import MetadataCatalog
from guardrail.logical_planner import LogicalPlanner, LogicalPlanningError
from guardrail.policy import load_policy
from guardrail.sql_generator import SQLGenerator
from scripts.validate_query_plan import validate_plan_data


ROOT = Path(__file__).resolve().parents[2]


def _plan() -> dict:
    for line in (ROOT / "benchmark" / "datasets" / "sql.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        if case["case_id"] == "SQL_S001":
            plan = deepcopy(case["input"]["plan"])
            plan.update(metrics=["customer_count"], dimensions=[], filters=[], group_by=[], having=[], order_by=[], time_range=None, limit=None)
            return plan
    raise AssertionError("SQL_S001 is missing")


def _entity_plan(target: str, value: str = "XX00000112") -> dict:
    plan = _plan()
    plan["filters"] = [{
        "id": "f1", "type": "entity", "target": target, "operator": "exists",
        "value": value, "source": "entity_resolution", "confidence": 1.0,
    }]
    plan["entities"] = [{
        "entity_type": target, "surface": target, "resolution_status": "resolved",
        "resolved": {"id": value, "name": target, "entity_type": target, "attributes": {}},
        "candidates": [], "confidence": 1.0, "source": "exact_match",
    }]
    return plan


def _compile(plan: dict):
    validation = validate_plan_data(plan)
    assert validation["valid"], validation["errors"]
    return SQLGenerator().generate("relation-hotfix", plan, validation)


def test_parent_branch_has_enabled_verified_mapping():
    catalog = MetadataCatalog()
    relation = catalog.entity_relation("parent_branch")
    assert relation["target_dimension"] == "parent_branch"
    assert catalog.verified_join_by_id(relation["verified_join"])["verified"] is True


def test_customer_to_branch_relation_uses_registered_dimension():
    artifact = _compile(_entity_plan("branch"))
    assert "d_branch.org_id AS branch" in artifact.sql


def test_branch_to_parent_branch_relation_uses_hierarchy_field():
    artifact = _compile(_entity_plan("parent_branch"))
    assert "d_branch.up_org_id AS parent_branch" in artifact.sql
    assert artifact.logical_plan["dimension_routes"]["parent_branch"]["path"] == ["ads_cust_info_d", "dim_branch"]


def test_invalid_parent_relation_path_is_rejected():
    catalog = MetadataCatalog()
    catalog.entity_relations["parent_branch"]["verified_join"] = "missing_join"
    planner = LogicalPlanner(catalog, load_policy("logical_mapping.yaml"))
    with pytest.raises(LogicalPlanningError) as caught:
        planner.build(_entity_plan("parent_branch"))
    assert caught.value.code == "UNVERIFIED_ENTITY_RELATION"


def test_unknown_relation_is_rejected_fail_closed():
    planner = LogicalPlanner(MetadataCatalog(), load_policy("logical_mapping.yaml"))
    with pytest.raises(LogicalPlanningError) as caught:
        planner.build(_entity_plan("invented_relation"))
    assert caught.value.code == "UNKNOWN_ENTITY_RELATION"


def test_unsafe_grain_strategy_is_rejected():
    catalog = MetadataCatalog()
    catalog.entity_relations["parent_branch"]["grain_strategy"] = "direct_one_to_many_join"
    planner = LogicalPlanner(catalog, load_policy("logical_mapping.yaml"))
    with pytest.raises(LogicalPlanningError) as caught:
        planner.build(_entity_plan("parent_branch"))
    assert caught.value.code == "RELATION_GRAIN_AMPLIFICATION"


def test_parent_branch_filter_is_parameterized():
    artifact = _compile(_entity_plan("parent_branch"))
    assert "WHERE d_branch.up_org_id = :p" in artifact.sql
    assert "XX00000112" not in artifact.sql
    assert "XX00000112" in artifact.params.values()


def test_branch_entity_not_found_is_reported():
    result = EntityTool().search("branch", "不存在营业部")
    assert result.data["status"] == "not_found"
    assert result.data["candidates"] == []


def test_ambiguous_branch_requires_clarification():
    result = EntityTool().search("branch", "北京******营业部")
    assert result.data["status"] == "ambiguous"
    assert len(result.data["candidates"]) > 1


def test_existing_branch_query_still_resolves_and_compiles():
    state = AgentOrchestrator().run("重庆******营业部客户有多少？")
    assert state.status == "ready"
    assert [item["entity_type"] for item in state.resolved_entities] == ["branch"]
    artifact = SQLGenerator().generate(state.query_id, state.query_plan, state.validation_result)
    assert "d_branch.org_id = :p" in artifact.sql


def test_parent_branch_type_hint_removes_same_surface_branch_duplicate():
    state = AgentOrchestrator().run("北京分公司客户有多少？")
    assert state.status == "ready"
    assert [item["entity_type"] for item in state.resolved_entities] == ["parent_branch"]
    assert [item["target"] for item in state.query_plan["filters"]] == ["parent_branch"]


def test_customer_count_remains_distinct_after_parent_branch_join():
    artifact = _compile(_entity_plan("parent_branch"))
    assert "SELECT DISTINCT c.pty_id AS pty_id" in artifact.sql
    assert "COUNT(DISTINCT b.pty_id) AS customer_count" in artifact.sql
