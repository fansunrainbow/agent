from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.loader import available_suites
from benchmark.reports import ReportWriter
from benchmark.runner import BenchmarkRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Stage 8 reproducible benchmark.")
    parser.add_argument("--suite", action="append", default=[], help="Suite name; repeat for multiple suites, or use all.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "benchmark" / "datasets")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    known = available_suites(args.dataset_dir)
    suites = args.suite or ["all"]
    invalid = sorted(set(suites) - set(known) - {"all"})
    if invalid:
        parser.error(f"unknown suite(s): {', '.join(invalid)}; available: {', '.join(known)}")
    output_dir = args.output_dir or ROOT / "benchmark" / "reports" / datetime.now().strftime("%Y%m%d_%H%M%S")
    report, outcomes = BenchmarkRunner(args.dataset_dir).run(suites)
    paths = ReportWriter(output_dir).write(report, outcomes)
    summary = {
        "total_cases": report["total_cases"],
        "failed": sum(not item.passed for item in outcomes),
        "mode": report["mode"],
        "reports": {key: str(value.resolve()) for key, value in paths.items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
