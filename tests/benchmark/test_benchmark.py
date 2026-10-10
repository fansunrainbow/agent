from __future__ import annotations

from pathlib import Path

import yaml

from benchmark.loader import available_suites, load_cases
from benchmark.metrics import set_scores
from benchmark.runner.benchmark_runner import BenchmarkRunner
from benchmark.rule_snapshot import check_rule_snapshot


def test_all_required_suites_exist_and_total_at_least_200():
    required = {"semantic", "query_plan", "sql", "result", "hallucination", "guardrail", "generalization", "multi_turn", "marketing", "end_to_end", "official_seed"}
    suites = set(available_suites())
    assert required <= suites
    assert sum(len(load_cases(suite)) for suite in required) >= 200


def test_case_ids_are_unique_across_benchmark():
    ids = [case.case_id for suite in available_suites() for case in load_cases(suite)]
    assert len(ids) == len(set(ids))


def test_official_seed_is_not_used_as_bulk_dataset():
    all_cases = [case for suite in available_suites() for case in load_cases(suite)]
    official = [case for case in all_cases if case.source == "official_seed"]
    assert len(official) == 7
    assert len(official) / len(all_cases) < 0.05


def test_empty_sets_are_an_exact_match():
    assert set_scores([], [])["f1"] == 1.0


def test_rule_snapshot_is_current():
    assert check_rule_snapshot()["passed"] is True


def test_operator_coverage_counts_semantic_operator_expectations():
    cases = [case for suite in available_suites() for case in load_cases(suite)]
    operators = BenchmarkRunner._coverage(cases)["operators"]
    assert "exists" in operators["tested_ids"]
    assert operators["covered"] == 6
    assert set(operators["implemented_ids"]) == set(operators["tested_ids"]) | set(operators["not_tested_ids"])
    assert operators["unsupported_ids"] == []


def test_gold_adjudication_records_required_evidence_fields():
    path = Path(__file__).resolve().parents[2] / "benchmark" / "adjudication" / "gold_adjudication.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {"case_id", "original_expected", "system_actual", "conflict_type", "evidence", "decision", "review_status"}
    assert data["dataset_case_count"] == 226
    assert all(required <= set(item) for item in data["adjudications"])
