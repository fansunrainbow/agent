# Release Manifest

| Field | Value |
|---|---|
| Release name | `agentic-marketing-final` |
| Release timestamp | `2026-10-08T23:17:45+08:00` |
| Git commit | `NOT_AVAILABLE` — 当前工作区不是 Git repository |
| Suggested Git tag | `agentic-marketing-final`（未创建；无 Git repository） |
| Frozen Gold SHA-256 | `602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD` |
| Gold review | 40/40 reviewed |
| Second Frozen Benchmark | 36/40 = 90.00%; SQL execution 36/40 = 90.00% |
| Remaining failures | RDB_M06, RDB_M07, RDB_C01, RDB_C11 — `COST_BLOCK` |
| Python tests | 241/241 PASS |
| Frontend tests | 14/14 PASS |
| Frontend build | PASS |
| Frontend REAL_DB E2E | PASS |
| Minute-level requirement | PASS |
| Agent final status | `AGENT_FINAL_READY = YES` |
| Package integrity | Per-file SHA-256 plus aggregate content digest in `SUBMISSION_CONTENTS.json` |

## Frozen artifacts

- `benchmark/datasets/real_db_gold.jsonl`
- `benchmark/reports/real_db_final/second_frozen_benchmark_report.json`
- `benchmark/reports/real_db_final/second_frozen_result_comparison.jsonl`
- `benchmark/reports/real_db_final/second_frozen_failure_cases.jsonl`
- `benchmark/reports/real_db_final/second_frozen_latency_report.json`
- `benchmark/reports/real_db_final/benchmark_delta_report.json`
- `benchmark/reports/real_db_final/frontend_real_db_e2e.json`

Core semantic, planning, SQL, Guardrail, Result Validator, Frozen Gold, and evaluator code are frozen. Any later core change requires proportional regression and Benchmark revalidation.

The post-freeze changes are delivery-only: pytest collection isolation, content-hashed packaging, portable import paths, controlled external-data verification, dependency pins, and localhost-only default serving. They do not change the frozen business execution path.
