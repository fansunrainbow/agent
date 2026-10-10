from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.final_real_db_runner import FinalRealDBBenchmarkRunner, frozen_integrity
from database import DatabaseConfig, create_readonly_connection


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen 40-case benchmark on real read-only MySQL")
    parser.add_argument("--cases", type=Path, default=ROOT / "benchmark" / "datasets" / "real_db_gold.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark" / "reports" / "real_db_final")
    args = parser.parse_args()
    integrity = frozen_integrity(args.cases)
    if not integrity["passed"]:
        raise SystemExit(f"GOLD_INTEGRITY failed: {integrity}")
    config = DatabaseConfig.from_env()
    if config.user != "agent_readonly_user":
        raise SystemExit(f"benchmark requires agent_readonly_user; configured user is {config.user!r}")
    connection = create_readonly_connection(config)
    capability = connection.capability_check()
    if not capability.readonly_verified:
        raise SystemExit("read-only capability check failed")
    runner = FinalRealDBBenchmarkRunner(connection)
    try:
        cases = runner.load(args.cases)
        report = runner.write(runner.run(cases), args.output, integrity)
        print(report)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
