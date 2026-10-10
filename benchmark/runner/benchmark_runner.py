from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from benchmark.loader import available_suites, load_cases
from benchmark.metrics import latency_summary
from benchmark.models import CaseOutcome
from benchmark.rule_snapshot import check_rule_snapshot
from guardrail.catalog import MetadataCatalog
from marketing.rule_registry import RuleRegistry
import yaml

from .case_runner import CaseRunner


class BenchmarkRunner:
    def __init__(self, dataset_dir: Path | None = None):
        self.dataset_dir = dataset_dir
        self.case_runner = CaseRunner()

    def run(self, suites: list[str]) -> tuple[dict[str, Any], list[CaseOutcome]]:
        if suites == ["all"]:
            suites = available_suites(self.dataset_dir) if self.dataset_dir else available_suites()
        outcomes: list[CaseOutcome] = []
        counts: dict[str, int] = {}
        sources: Counter[str] = Counter()
        difficulty: Counter[str] = Counter()
        coverage_input: list[Any] = []
        for suite in suites:
            cases = load_cases(suite, self.dataset_dir) if self.dataset_dir else load_cases(suite)
            counts[suite] = len(cases)
            for case in cases:
                sources[case.source] += 1
                difficulty[case.difficulty] += 1
                coverage_input.append(case)
                outcome = self.case_runner.run(suite, case)
                outcomes.append(outcome.model_copy(update={"case_input": {"query": case.query, "turns": case.turns, "input": case.input}}))
        report = self._aggregate(outcomes, counts, sources, difficulty, coverage_input)
        return report, outcomes

    @staticmethod
    def _aggregate(outcomes, counts, sources, difficulty, cases) -> dict[str, Any]:
        by_suite: dict[str, list[CaseOutcome]] = defaultdict(list)
        for outcome in outcomes:
            by_suite[outcome.suite].append(outcome)
        suite_reports = {}
        all_latency: dict[str, list[float]] = defaultdict(list)
        for suite, items in by_suite.items():
            metric_values: dict[str, list[float]] = defaultdict(list)
            for item in items:
                for name, value in item.metrics.items():
                    if isinstance(value, (int, float)):
                        metric_values[name].append(float(value))
                for stage, value in item.latency_ms.items():
                    all_latency[stage].append(value)
            suite_reports[suite] = {
                "case_count": len(items),
                "passed": sum(item.passed for item in items),
                "failed": sum(not item.passed for item in items),
                "accuracy": sum(item.passed for item in items) / len(items) if items else 0,
                "average_score": fmean(item.score for item in items) if items else 0,
                "metrics": {name: fmean(values) for name, values in sorted(metric_values.items())},
            }
        failures = [item for item in outcomes if not item.passed]
        official = sources.get("official_seed", 0)
        generalization = sources.get("generalization", 0)
        total = len(outcomes)
        passed_count = sum(item.passed for item in outcomes)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": {"dry_run": True, "real_db": False, "execution_accuracy": "not_measured", "execution_equivalence": "not_measured"},
            "total_cases": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "overall_accuracy": passed_count / total if total else 0.0,
            "suite_counts": counts,
            "source_counts": dict(sources),
            "difficulty_counts": dict(difficulty),
            "official_ratio": official / total if total else 0,
            "generalization_ratio": generalization / total if total else 0,
            "suites": suite_reports,
            "latency": {stage: latency_summary(values) for stage, values in sorted(all_latency.items())},
            "failure_distribution": dict(Counter(item.failure_type or "UNKNOWN" for item in failures)),
            "top_failures": [{"case_id": item.case_id, "suite": item.suite, "failure_type": item.failure_type, "stage": item.stage, "notes": item.notes} for item in failures[:20]],
            "case_results": [{"case_id": item.case_id, "suite": item.suite, "passed": item.passed, "score": item.score, "failure_type": item.failure_type, "latency_ms": item.latency_ms, "metrics": item.metrics, "trace_id": item.trace_id} for item in outcomes],
            "coverage": BenchmarkRunner._coverage(cases),
            "stability": BenchmarkRunner._stability(outcomes),
            "repair": BenchmarkRunner._repair(outcomes),
            "clarification": BenchmarkRunner._clarification(outcomes),
            "rule_snapshot": check_rule_snapshot(),
        }

    @staticmethod
    def _coverage(cases) -> dict[str, Any]:
        metrics, dimensions, intents, operators, entities, marketing_rules = set(), set(), set(), set(), set(), set()
        def filters(nodes):
            for node in nodes:
                if "logic" in node:
                    yield from filters(node.get("conditions", []))
                else:
                    yield node
        for case in cases:
            plan = case.expected.get("plan", case.expected)
            metrics.update(plan.get("metrics", [])); dimensions.update(plan.get("dimensions", []))
            if plan.get("intent"): intents.add(plan["intent"])
            operators.update(case.expected.get("operators", []))
            coverage_plans = [plan]
            input_plan = case.input.get("plan")
            if isinstance(input_plan, dict):
                coverage_plans.append(input_plan)
            for coverage_plan in coverage_plans:
                for item in filters(coverage_plan.get("filters", [])):
                    if item.get("operator"): operators.add(item["operator"])
            entities.update(item.get("entity_type") for item in plan.get("entities", []) if isinstance(item, dict) and item.get("entity_type"))
            entities.update(case.expected.get("entity_types", []))
            if case.category == "marketing":
                target = case.input.get("target")
                kind = {"tags": "tag", "segment": "segment", "opportunities": "opportunity", "strategies": "strategy", "explanation": "opportunity"}.get(target)
                if kind and case.input.get("rule_id"):
                    marketing_rules.add(f"{kind}:{case.input['rule_id']}")
                if kind:
                    marketing_rules.update(f"{kind}:{rule_id}" for rule_id in case.expected.get("ids", []))
        catalog = MetadataCatalog()
        with (catalog.metadata_dir / "intent_registry.yaml").open("r", encoding="utf-8") as handle:
            all_intents = set((yaml.safe_load(handle) or {}).get("intents", {}))
        with (catalog.metadata_dir / "operator_registry.yaml").open("r", encoding="utf-8") as handle:
            all_operators = set((yaml.safe_load(handle) or {}).get("operators", {}))
        all_entities = set(catalog.entity_rules.get("entities", {}))
        rules = RuleRegistry()
        all_marketing_rules = {f"{kind}:{rule_id}" for kind in ("tag", "segment", "opportunity", "strategy") for rule_id in rules.load(kind)}

        def item(covered: set[str], registered: set[str]) -> dict[str, Any]:
            known = covered & registered
            return {
                "covered": len(known), "total": len(registered),
                "rate": len(known) / len(registered) if registered else 0.0,
                "covered_ids": sorted(known), "uncovered_ids": sorted(registered - known),
            }

        operator_coverage = item(operators, all_operators)
        operator_coverage.update({
            "implemented_ids": sorted(all_operators),
            "tested_ids": operator_coverage["covered_ids"],
            "not_tested_ids": operator_coverage["uncovered_ids"],
            "unsupported_ids": [],
        })
        return {
            "metrics": item(metrics, set(catalog.metrics)),
            "dimensions": item(dimensions, set(catalog.dimensions)),
            "intents": item(intents, all_intents),
            "operators": operator_coverage,
            "entities": item(entities, all_entities),
            "marketing_rules": item(marketing_rules, all_marketing_rules),
        }

    @staticmethod
    def _stability(outcomes) -> dict[str, float | int]:
        values = [item.metrics.get("output_stability_accuracy") for item in outcomes if "output_stability_accuracy" in item.metrics]
        return {"case_count": len(values), "output_stability_rate": fmean(values) if values else 0.0}

    @staticmethod
    def _repair(outcomes) -> dict[str, float | int]:
        values = [float(item.metrics.get("repair_count", 0)) for item in outcomes if "repair_count" in item.metrics]
        return {"case_count": len(values), "average_repair_count": fmean(values) if values else 0.0, "max_repair_count": max(values) if values else 0.0}

    @staticmethod
    def _clarification(outcomes) -> dict[str, float | int]:
        values = [float(item.metrics.get("clarification", 0)) for item in outcomes if "clarification" in item.metrics]
        return {"case_count": len(values), "clarification_rate": fmean(values) if values else 0.0}
