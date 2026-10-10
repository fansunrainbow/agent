# Final Real-DB Remediation Report

## Scope and integrity

- Completed PHASE 1 through PHASE 17 only.
- The second 40-case Frozen Benchmark was not run.
- Frozen Gold SHA-256 remains `602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD`.
- Frozen Gold SQL, query text, difficulty, and case IDs were not changed.

## 1. Failure root-cause distribution

The 22 original failures were frozen before production changes:

| Root cause | Count |
|---|---:|
| ENUM_VALUE_NORMALIZATION | 6 |
| OUTPUT_SHAPE | 3 |
| EXISTS_GUARDRAIL_CONTRACT | 3 |
| JOIN_COST_EXPLOSION | 3 |
| TIME_END_OF_PERIOD | 2 |
| METRIC_AGGREGATION | 2 |
| TIME_MONTH_BUCKET | 1 |
| HAVING_PLACEMENT | 1 |
| OTHER | 1 |

Detailed evidence is in `docs/final_real_db_failure_analysis.md` and
`benchmark/reports/real_db_final/failure_root_causes.json`.

## 2. Modified modules

- Semantic planning: `agent/planner.py`, `agent/services/condition_grounder.py`,
  `agent/services/entity_resolver.py`, `agent/tools/dimension_tool.py`,
  `agent/orchestrator.py`.
- Metadata: `metadata/value_mappings.yaml`.
- SQL and Guardrail: `guardrail/catalog.py`, `guardrail/sql_generator.py`,
  `guardrail/parser/sql_ast.py`, `guardrail/schema_guard.py`,
  `guardrail/result_normalizer.py`, `guardrail/execution_manager.py`, and
  `guardrail/policies/sql_policy.yaml`.
- Benchmark isolation: `benchmark/loader.py`.
- Real UI/API wiring: `webapp/service.py`, `webapp/api.py`,
  `frontend/src/main.jsx`.
- Verification: `scripts/run_targeted_real_db_remediation.py`,
  `scripts/run_final_frontend_e2e.py`, and generic regression tests.

## 3. Enum normalization

Implemented one registry-driven chain: raw input -> canonical semantic value in
Query Plan -> database storage value in parameterized SQL. It covers gender,
customer level/status, product category, city suffix normalization, and other
registered dimensions. Query Plans now retain values such as `female`, `gold`,
and `stock`, while SQL binds `5000003`, `1000003`, and `股票` respectively.

## 4. Aggregation and output shape

Metric questions preserve aggregate output, customer selection preserves entity
IDs, and ranking preserves ID plus metric. Implicit positive segment filters are
no longer invented for plain metric questions.

## 5. HAVING

Aggregate metric predicates are classified from metric metadata and moved to
HAVING (or evaluated against a pre-aggregated CTE), while row-level dimension
predicates remain in WHERE.

## 6. Time compiler

Period start/end wrappers are resolved consistently. Snapshot metrics select the
actual MIN/MAX available fact date within the requested period instead of
assuming that every fact table contains the calendar boundary date.

## 7. Time series

Trend plans compile registered day/month/quarter buckets with deterministic
GROUP BY and ORDER BY and return stable time-series rows.

## 8. EXISTS contract

Known correlated EXISTS/NOT EXISTS relations pass the compiler, AST, Security,
Schema, and Join guards. Unknown relations remain blocked. Product-category
relations use deduplicated semi-joins, and negative holding intent remains
NOT EXISTS rather than being rewritten as a numeric threshold.

## 9. Cost optimization

No threshold was raised. Filters are pushed into base entities and fact CTEs;
product joins use deduplicated semi-joins; snapshot facts are reduced to the
effective date; and relationship filters avoid direct many-to-many expansion.

| Original cost case | Before estimated rows | After estimated rows | Targeted result |
|---|---:|---:|---|
| RDB_C01 | 18,362,885,064 | 2,545,682 | Still blocked by the unchanged 1M guard |
| RDB_C02 | 159,280,285 | 504,685 | Correct |
| RDB_C05 | 29,219,610 | 475,306 | Correct |

The remaining targeted cost blocks are RDB_M06, RDB_M07, RDB_C01, and RDB_C11.
They were fail-closed and no unsafe execution was allowed.

## 10. Ranking

Ranking output is per entity, ordered by the requested metric and direction,
then by stable `pty_id ASC`, with parameterized Top-K limiting.

## 11. Result normalization

All database rows pass through a shared normalizer for Decimal, date/datetime,
NULL, tuples/mappings, and stable set/grouped/time-series ordering. Ranking order
is preserved.

## 12. Benchmark loader

Legacy benchmark suites now use an explicit registry. `real_db_gold.jsonl` is no
longer parsed as a legacy `BenchmarkCase` dataset.

## 13. Frontend real execution

REAL_DB mode sends `execute: true` through the natural-language Agent ->
Guardrail -> read-only DB chain. No raw SQL endpoint was added. The UI displays
Query Plan, generated SQL, parameters, Guardrail, final result, validation, and
latency.

## 14. Customer 360 and Marketing

Customer 360, segment evaluation, opportunity discovery, and strategy output are
wired to real Stage 6 safe results and Stage 7 services. Failures are explicit;
there is no demo-fixture fallback in REAL_DB mode.

## 15. Tests added or extended

Generic coverage now includes enum normalization, aggregation/output shape,
HAVING, period end, monthly time series, EXISTS/NOT EXISTS, deduplicated product
semi-joins, ranking tie order, result normalization, loader isolation, REAL_DB UI
requests, final result rendering, Customer 360, and marketing wiring.

## 16. Full regression

- Python: **240 passed**, 0 failed, 0 errors.
- Frontend: **14 passed**, 0 failed.
- Frontend production build: **PASS**.
- Frontend/API REAL_DB E2E: **PASS**, 14 scenarios.

## 17. Targeted 22-case verification

- Scope: only the 22 failures from the first Frozen run.
- Before: **0/22 correct**, SQL execution success **12/22**.
- After: **18/22 correct**, SQL execution success **18/22**.
- Remaining: RDB_M06, RDB_M07, RDB_C01, RDB_C11 (all COST_BLOCK).
- Detailed per-case before/after evidence:
  `benchmark/reports/real_db_final/targeted_remediation_verification.json`.

## 18. Second Frozen Benchmark gate

The targeted failures clearly decreased, full regression passed, frontend real
execution passed, and Frozen Gold integrity passed.

**SECOND_FROZEN_BENCHMARK_READY = YES**

The second Frozen Benchmark has deliberately not been started.
