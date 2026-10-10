from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.loader import load_cases
from benchmark.runner.case_runner import CaseRunner


SELECTION = {
    "semantic": ["SEM_S001", "SEM_S003", "SEM_M001", "SEM_E001"],
    "generalization": ["GEN_MX100", "GEN_MX105", "GEN_X001", "GEN_X007"],
    "multi_turn": ["MT_002", "MT_003", "MT_006"],
    "sql": ["SQL_S001", "SQL_M001", "SQL_C010"],
    "hallucination": ["HALL_AGENT_001", "HALL_SQL_001", "HALL_MKT_ATTR_001"],
    "marketing": ["MKT_001", "MKT_010", "MKT_020"],
}


def stable_payload(outcome) -> str:
    actual = dict(outcome.actual)
    actual.pop("_comparison", None)
    return json.dumps({
        "passed": outcome.passed,
        "score": outcome.score,
        "metrics": outcome.metrics,
        "actual": actual,
        "failure_type": outcome.failure_type,
        "stage": outcome.stage,
    }, ensure_ascii=False, sort_keys=True, default=str)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen 20-case, three-repeat stability sample.")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark" / "reports" / "stage8_6_frozen" / "stability_report.json")
    args = parser.parse_args()
    runner = CaseRunner()
    results = []
    for suite, ids in SELECTION.items():
        cases = {case.case_id: case for case in load_cases(suite)}
        for case_id in ids:
            if case_id not in cases:
                raise KeyError(f"missing stability case: {case_id}")
            outputs = [stable_payload(runner.run(suite, cases[case_id])) for _ in range(3)]
            results.append({
                "case_id": case_id, "suite": suite, "repeats": 3,
                "stable": len(set(outputs)) == 1,
                "unique_output_count": len(set(outputs)),
            })
    stable_count = sum(item["stable"] for item in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": "local deterministic dry-run; real_db=false",
        "case_count": len(results), "repeat_count": 3,
        "output_stability_rate": stable_count / len(results),
        "stable_cases": stable_count, "unstable_cases": len(results) - stable_count,
        "suite_case_counts": {suite: len(ids) for suite, ids in SELECTION.items()},
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "stability": report["output_stability_rate"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
