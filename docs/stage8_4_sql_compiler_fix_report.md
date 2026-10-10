# Stage 8.4 — SQL Compiler Coverage Fix Report

## 1. Conclusion

Stage 8.4 is complete. SQL Benchmark improved from **8/15 (53.33%)** to **14/15 (93.33%)**, End-to-End dry-run improved from **12/20 (60.00%)** to **17/20 (85.00%)**, and the full Benchmark improved from **155/226** to **166/226**. The remaining SQL case is an intentionally rejected unexpanded Concept, not a compiler crash or unsafe simplification.

No Stage 8.2 semantic grounding, Stage 8.3 canonicalizer, Benchmark expected/case, multi-turn patch behavior, or Stage 7 marketing rule was changed. No SQL path uses a query string, Benchmark case ID, or metric-name template.

## 2. Files

### Modified

- `metadata/metrics.yaml`
- `guardrail/logical_planner.py`
- `guardrail/sql_generator.py`

### Added

- `tests/guardrail/test_stage84_sql_compiler.py`
- `docs/stage8_4_sql_compiler_fix_report.md`
- `benchmark/reports/stage8_4_sql_compiler_fix/`

## 3. Compiler architecture

The execution path remains:

`Validated Query Plan → registry-backed LogicalPlan → parameterized physical SQL → Stage 6 SQL Validator`

`LogicalPlan` now records required metrics, dimensions, tables, joins, filters, time filters, group-by, having, order-by, limit, metric grains, dimension routes, and output grain. Physical compilation enriches it with the exact verified dimension routes, time-filtered tables, parameter names, and metric registry contracts.

Production execution still receives the original validated Query Plan. Unsupported combinations raise a controlled `SQLGenerationError`; the compiler never removes metrics, filters, or time ranges to make a plan executable.

## 4. Metric Compiler

`customer_count` now declares `source_fields: [pty_id]`, `aggregation.default: count_distinct`, `aggregation.outer: count_distinct`, and `distinct_key: pty_id` in metadata. The generic compiler uses that contract to produce `COUNT(DISTINCT ...)`; the former Python metric-ID special case was removed.

Supported aggregation classes are:

- `COUNT`
- `COUNT_DISTINCT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`
- metadata expressions with custom aggregation
- dependency-based ratio and derived expressions
- period-first and period-last snapshot metrics

All **38/38** registered metrics compile successfully in the registry audit. Expressions and dependencies come from `metrics.yaml`; formulas are not redefined in Python.

## 5. Multi-metric and pre-aggregation

Each leaf metric is compiled into its own CTE at a declared customer-compatible grain. Derived metrics join only their already aggregated dependencies. Multiple fact sources are never joined at detail grain: asset, trade, flow, and holding CTEs are aggregated independently, then merged through their `pty_id` result grain.

Logical provenance marks these fact-to-fact combinations as `preaggregated: true`, allowing Schema/Join Guard to verify that the compiler did not create a direct fact-detail join.

## 6. Dimension Compiler and Join Resolver

Supported routes are:

- Customer-master dimensions: directly from `ads_cust_info_d` registered fields.
- Branch and parent-branch dimensions: `ads_cust_info_d ↔ dim_branch` through the verified `org_id` edge.
- Product name/category/type/market dimensions: `ads_cust_info_d ↔ holding/transaction fact ↔ dim_product`, with both edges required to be verified.

Customer-to-product direct joins are never generated. Product dimensions require exactly one provable fact bridge; zero or multiple incompatible bridges return `SQL_UNSUPPORTED_COMBINATION`. Missing dimension fields or unverified edges are rejected rather than guessed.

## 7. Filter and aggregation coverage

Scalar and set/range operators supported by the compiler:

- `eq`, `neq`, `gt`, `gte`, `lt`, `lte`
- `in`, `not_in`, `between`
- `contains`, `starts_with`, `ends_with`
- `is_null`, `is_not_null`
- registered entity-relation `exists`, `not_exists` using correlated `EXISTS`/`NOT EXISTS`

Business values, time bounds, filter lists, patterns, thresholds, and limits remain parameters. Grouped metric predicates compile to `HAVING`, dimension predicates compile to `WHERE`, and ranking/top-k compile to validated `ORDER BY` plus parameterized `LIMIT`.

An unexpanded `type=concept` filter is rejected with `SQL_UNSUPPORTED_COMBINATION`. SQL compilation does not reinterpret business vocabulary; the concept must first be expanded into a validated dimension/entity filter by an earlier stage.

## 8. Time and grain safety

Every fact CTE reads its registered time field from `tables.yaml`; no global date-column assumption was introduced. Product bridge rows use that bridge table's registered time field as well.

The logical plan records metric grains and output grain. Customer and Branch analysis require metrics that can safely reduce to customer/customer-group grain. Product grouping requires a shared verified product-capable fact bridge. Incompatible product/multi-fact combinations, unsupported subjects, ambiguous grain conversions, and missing join paths fail closed.

## 9. Tests and regression

Stage 8.4 adds **21 test functions**:

- the 20 requested scenarios: customer count, city filter, grouped count, average asset, trade amount, dual metrics, Branch, Product category, `between`, `in`, `not_in`, `exists`, `not_exists`, group-by, having, ranking, top-k, multi-fact pre-aggregation, invalid join rejection, and unsupported-combination rejection;
- one complete **38-metric registry audit**.

Final regression:

- Stage 4 Query Plan: **12/12**
- Agent/Stage 5 including Stage 8.2: **46/46**
- Stage 8.3 Benchmark/canonicalization tests: **27/27**
- Stage 6 Guardrail including Stage 8.4: **43/43**
- Stage 7 Marketing: **24/24**
- Full repository: **152/152**
- Guardrail Benchmark: **20/20**, with zero false positives and zero false negatives

## 10. Benchmark before/after

| Metric | Before Stage 8.4 | After Stage 8.4 |
|---|---:|---:|
| SQL Compile Success | 8/15 (53.33%) | **14/15 (93.33%)** |
| SQL dry-run case accuracy | 8/15 (53.33%) | **14/15 (93.33%)** |
| Schema validity among compiled SQL | 100.00% | **100.00%** |
| Join validity among compiled SQL | 100.00% | **100.00%** |
| Parameterized-value accuracy among compiled SQL | 100.00% | **100.00%** |
| Guard allowed among expected-safe compiled SQL | 100.00% | **100.00%** |
| End-to-End dry-run | 12/20 (60.00%) | **17/20 (85.00%)** |
| Total Benchmark passed | 155/226 | **166/226** |
| Failure count | 71 | **60** |
| Semantic accuracy | 83.33% | **83.33%** |
| Hallucination | 20/20 | **20/20** |

Benchmark mode remains `real_db=false`. SQL execution accuracy and production result equivalence remain `not_measured`; dry-run validation is not presented as real database execution.

## 11. Remaining SQL root causes

One SQL Benchmark failure remains:

- `SQL_C002` — `SQL_UNSUPPORTED_COMBINATION`: the plan contains an unexpanded `diamond_customer` Concept. Compiling it would require the SQL layer to reinterpret a business concept, explicitly forbidden in Stage 8.4.

The three remaining End-to-End failures (`E2E_CLARIFY_003`, `E2E_CLARIFY_006`, `E2E_CLARIFY_007`) are pre-SQL clarification-versus-unsupported state differences. They do not reach SQL generation and are outside this stage.

No new Schema, Join, Security, Cost, Parameter, Semantic, Canonicalization, Hallucination, or Marketing regression was introduced.

## 12. Stage 8.5 readiness

The project can proceed to **Stage 8.5 — Multi-turn Patch Fix**. Customer-count compilation is metadata-driven, all registered metrics pass the compiler audit, multi-fact plans retain pre-aggregation, Branch/Product routes are verified, filter/group/having/ranking coverage is expanded, and all generated SQL still passes the complete Stage 6 guard chain.

## 13. Evidence

- Full JSON: `benchmark/reports/stage8_4_sql_compiler_fix/benchmark_report.json`
- Full Markdown: `benchmark/reports/stage8_4_sql_compiler_fix/benchmark_report.md`
- Full failures: `benchmark/reports/stage8_4_sql_compiler_fix/failure_cases.jsonl`
- Targeted JSON: `benchmark/reports/stage8_4_sql_compiler_fix/targeted/benchmark_report.json`
- Targeted failures: `benchmark/reports/stage8_4_sql_compiler_fix/targeted/failure_cases.jsonl`
