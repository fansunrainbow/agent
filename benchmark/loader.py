from __future__ import annotations

import json
from pathlib import Path

from .models import BenchmarkCase


DATASET_DIR = Path(__file__).resolve().parent / "datasets"
LEGACY_SUITES = {
    "end_to_end", "generalization", "guardrail", "hallucination", "marketing",
    "multi_turn", "official_seed", "query_plan", "result", "semantic", "sql",
}


def load_cases(suite: str, dataset_dir: Path = DATASET_DIR) -> list[BenchmarkCase]:
    path = dataset_dir / f"{suite}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"benchmark dataset not found: {path}")
    cases: list[BenchmarkCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    cases.append(BenchmarkCase.model_validate_json(line))
                except Exception as exc:
                    raise ValueError(f"invalid case at {path.name}:{line_number}: {exc}") from exc
    seen: set[str] = set()
    duplicates = [case.case_id for case in cases if case.case_id in seen or seen.add(case.case_id)]
    if duplicates:
        raise ValueError(f"duplicate case ids in {path.name}: {duplicates}")
    return cases


def available_suites(dataset_dir: Path = DATASET_DIR) -> list[str]:
    return sorted(path.stem for path in dataset_dir.glob("*.jsonl") if path.stem in LEGACY_SUITES)
