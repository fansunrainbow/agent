# Stage 8 Benchmark

This directory is the fixed, reproducible evaluation layer for Stages 1–7. It does not change business behavior and does not generate production SQL outside the existing Stage 4 validation and Stage 6 guardrail path.

## Run

```powershell
python scripts/run_benchmark.py --suite all
python scripts/run_benchmark.py --suite semantic
python scripts/run_benchmark.py --suite query_plan
python scripts/run_benchmark.py --suite sql
python scripts/run_benchmark.py --suite result
python scripts/run_benchmark.py --suite hallucination
python scripts/run_benchmark.py --suite guardrail
python scripts/run_benchmark.py --suite generalization
python scripts/run_benchmark.py --suite multi_turn
python scripts/run_benchmark.py --suite marketing
python scripts/run_benchmark.py --suite end_to_end
```

Use `--suite` more than once to combine suites. Use `--output-dir <path>` for a stable report location.

Every run writes `benchmark_report.json`, `benchmark_report.md`, and `failure_cases.jsonl`. SQL execution and production-result equivalence are explicitly marked `not_measured` while no real database is configured; dry-run success must not be read as database execution success.

The committed JSONL datasets are the evaluation inputs. Rebuild them only when intentionally revising the benchmark contract:

```powershell
python -m benchmark.build_datasets
```

Official Q&A examples are seed cases only. Generalization, adversarial, and human-reviewed marketing cases are maintained separately. Rule snapshot drift is reported and must be reviewed rather than silently accepted.
