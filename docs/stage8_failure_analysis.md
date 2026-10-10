# Stage 8.1 — Benchmark-driven Failure Analysis

## 1. Scope and evidence

This analysis uses the frozen Stage 8 final outputs:

- `benchmark/reports/stage8_final/failure_cases.jsonl`
- `benchmark/reports/stage8_final/benchmark_report.json`
- `benchmark/reports/stage8_final/benchmark_report.md`

Stage 3 Business Dictionary, Stage 4 Query Plan, Stage 5 Agent Core, and Stage 6 Guardrail were inspected only to interpret failures. No Stage 1–8 core logic, benchmark `expected`, case-specific behavior, or official-Q&A special rule was changed.

All 105 failure rows are individually classified in `failure_clusters.json`. A failure has exactly one primary root cause, one A/B/C nature, and may have secondary causes. Counts below use the primary cause so they reconcile to 105 without double counting.

## 2. Executive conclusion

| Failure nature | Count | Percentage |
|---|---:|---:|
| A. REAL_SYSTEM_DEFECT | 55 | 52.38% |
| B. EVALUATION_DEFECT | 27 | 25.71% |
| C. AMBIGUOUS | 23 | 21.90% |
| **Total** | **105** | **100.00%** |

The 105 failures are not 105 independent product defects. The largest single cluster is a mixed Gold/system issue: 21 generalization probes omit time in the query but hard-code `2026 Q1 + ready` in Gold. Clarification is correct under the low-hallucination rule, while failure to link the explicit registered metric ID is independently a system defect. These rows require Gold adjudication before they can measure ready/clarify accuracy.

The system defects with the broadest impact are time parsing, typed semantic linking, entity resolution, registered aggregate compilation, intent/unsupported routing, and deterministic multi-turn replacement/removal. The largest evaluator defects are implicit `customer` dimension mismatches, concept-versus-dimension expansion, redundant grouping markers, and enum display value versus canonical code.

## 3. Root-cause clusters

| Root cause | Count | Percentage |
|---|---:|---:|
| GOLD_SCHEMA_MISMATCH | 23 | 21.90% |
| SEMANTIC_EQUIVALENCE_NOT_NORMALIZED | 17 | 16.19% |
| TIME_PARSING | 10 | 9.52% |
| SQL_METRIC_COMPILER | 8 | 7.62% |
| PLAN_NORMALIZATION_ERROR | 7 | 6.67% |
| PLAN_SEMANTIC_ERROR | 6 | 5.71% |
| SEMANTIC_METRIC_LINKING | 5 | 4.76% |
| SEMANTIC_CONCEPT_LINKING | 5 | 4.76% |
| ENTITY_RESOLUTION | 5 | 4.76% |
| INTENT_CLASSIFICATION | 4 | 3.81% |
| PLAN_STRUCTURE_MISMATCH | 3 | 2.86% |
| SEMANTIC_DIMENSION_LINKING | 2 | 1.90% |
| UNSUPPORTED_HANDLING | 2 | 1.90% |
| MULTI_TURN_REPLACE | 2 | 1.90% |
| SQL_JOIN_RESOLUTION | 2 | 1.90% |
| CLARIFICATION_ERROR | 1 | 0.95% |
| MULTI_TURN_REMOVE | 1 | 0.95% |
| SQL_FILTER_COMPILER | 1 | 0.95% |
| SQL_UNSUPPORTED_COMBINATION | 1 | 0.95% |

No failure has the following as its primary root cause: `OPERATOR_PARSING`, `PLAN_PATCH_ERROR`, `SQL_DIMENSION_COMPILER`, `SQL_AGGREGATION`, `SQL_TIME_FILTER`, `SQL_PARAMETERIZATION`, `MULTI_TURN_ADD`, `MULTI_TURN_CONTEXT_RETENTION`, `EVALUATOR_TOO_STRICT`, or `OTHER`. This does not prove those capabilities are complete; several are not independently covered.

## 4. Why Query Plan Exact Match is 0%

The 30 Query Plan cases divide cleanly into:

| Nature of mismatch | Count | Share of 30 |
|---|---:|---:|
| Genuine semantic error | 20 | 66.67% |
| Structure-only difference | 3 | 10.00% |
| Canonicalization-only difference | 7 | 23.33% |

Therefore, Exact Match is zero for two different reasons: 20 plans genuinely lose or change semantics, while 10 plans are rejected despite being structurally or semantically equivalent enough for execution.

Important checks against the evaluator implementation:

- `output`, default output values, `assumptions`, and `confidence` are not in `PLAN_FIELDS`; they did not cause the 0% result.
- Metric, dimension, group-by, top-level filter, entity, and order lists are already sorted; ordinary field or entity order did not cause the failures.
- Empty arrays are normalized consistently in the compared fields. `null` versus `[]` is not the dominant cause.
- Missing `time_range` versus a requested quarter is a semantic loss, not formatting.
- The evaluator does not canonicalize implicit `customer` dimensions, concept-to-dimension/value expansion, enum code versus display value, redundant grouping-marker concepts, or equivalent detail/group interpretations.
- End-of-period/start-of-period and an entire quarter are not automatically equivalent and should remain semantic mismatches.

The 20 genuine errors are dominated by missing/wrong metrics, lost time ranges, dropped age/concept predicates, and changed Boolean trees. The three structure-only cases add only the implicit `customer` dimension. The seven canonicalization cases compare registered concepts with deterministic expansions or treat grouping markers as executable filters.

The 0% raw score is thus too pessimistic, but it is not merely an evaluator artifact. A future report should show both raw exact match and canonical semantic match. The Agent should not be changed solely to satisfy raw structural equality.

## 5. Semantic failure clustering

The Semantic suite has 22 failures out of 30, producing 26.67% case-level exact accuracy. Its component metrics are much stronger: Metric F1 `1.0000`, time accuracy `1.0000`, intent accuracy `0.8667`, dimension F1 `0.5933`, operator F1 `0.7333`, and entity F1 `0.8333`.

Primary clusters within the 22 Semantic-suite failures:

| Cluster | Count | Interpretation |
|---|---:|---|
| SEMANTIC_EQUIVALENCE_NOT_NORMALIZED | 11 | Extra implicit `customer` output dimension; evaluator false negatives |
| ENTITY_RESOLUTION | 5 | Controlled entity IDs were not resolved |
| INTENT_CLASSIFICATION | 3 | Product-category lookup became customer selection |
| SEMANTIC_CONCEPT_LINKING | 3 | Grouping phrase became a synthetic equality concept/filter |

`OPERATOR_PARSING` occurs as a secondary symptom in the last three cases because the synthetic concept introduces an unwanted `eq`. There are no primary metric-linking or time-parsing failures in the 30-case Semantic suite. One entity case also produces an unnecessary clarification, but entity resolution is the earlier root cause.

After separating the 11 evaluator-only failures, the suite contains 11 real system failures. A diagnostic, non-official adjusted view would be 19/30 semantically acceptable cases (63.33%), not 26.67%. The frozen official score must remain 26.67% until a versioned canonical evaluator is introduced.

The seven official-seed failures are reported separately: four time-parsing defects, one implicit-dimension evaluator mismatch, one custom-age-band Gold mismatch, and one ambiguous assumption that “analysis statistics” necessarily means `customer_count`.

## 6. Generalization failure analysis

- Raw Exact Match: `3/30 = 10.00%`
- Component F1: `0.7045`
- Raw ready/clarify/unsupported correctness: `8/30 = 26.67%`
- Gold status distribution: 30 ready, 0 clarify, 0 unsupported
- Actual failed status distribution: 22 needs-clarification, 5 ready

The 22 apparent false clarifications require separation:

1. `GEN_MX100`–`GEN_MX120` (21 cases) say only “query registered metric `<metric_id>`”. Their Gold injects 2026 Q1 even though the query contains no time and marks the plan ready. For time-required metrics, clarification is the low-hallucination behavior. At the same time, the Agent fails to preserve/link the exact registered metric ID. These cases are mixed and marked `AMBIGUOUS`, with `GOLD_SCHEMA_MISMATCH` primary and `SEMANTIC_METRIC_LINKING` secondary.
2. `GEN_X002` is the remaining real false clarification: diamond-customer city distribution loses count/group semantics.

If the 21 missing-time Gold conflicts were adjudicated as clarification cases, status correctness would be `29/30 = 96.67%`. This is a counterfactual diagnostic only; no expected value was changed.

Among the nine non-MX cases, three pass exactly, three are evaluator/canonicalization defects, one is ambiguous, and two are real generalization failures. The strict 10% score is therefore heavily depressed by Gold and canonicalization issues, but exact-ID linking, monthly trend intent, and grouped segment semantics remain genuine generalization gaps.

## 7. SQL failure analysis

There are seven SQL-suite failures and five end-to-end failures, for 12 failure rows. Several repeat the same capability defect across layers.

| SQL capability | Failure rows |
|---|---:|
| Metric Compiler | 8 |
| Join Resolver | 2 |
| Filter Compiler | 1 |
| Unsupported Combination | 1 |
| Dimension Compiler | 0 primary |
| Aggregation | 0 independent primary |
| Time Filter | 0 |
| Parameterization | 0 |

Detailed findings:

- `customer_count`: eight rows fail because the registered aggregate expression is rejected as containing an unregistered identifier. This is a generic metric-expression compiler defect, not a need for query templates.
- Multi Metric: the SQL suite does not independently exercise enough multi-metric combinations to make a reliable capability claim. This is a dataset gap.
- `group_by`: customer-count group cases fail before group compilation can be judged independently. Group-by coverage is confounded by the metric compiler.
- `having`: several metric-threshold plans compile successfully, indicating the basic metric-filter/HAVING route works, but coverage is narrow.
- Entity/concept filter: `diamond_customer` fails because no deterministic concept-to-dimension compiler mapping is available.
- Join resolution: registered `branch`/`parent_branch` analyses lack a safe verified path or supported grain.
- Time filter: fact-query successes pass Cost Guard; there is no primary time-filter compiler failure in this dataset.
- Parameterization: no benchmark failure is caused by missing parameterization.

Any repair must compile registry metadata and verified joins generically and must continue through Stage 4 validation plus Stage 6 Schema, Join, Cost, and Parameter guards.

## 8. Multi-turn analysis

Five of ten cases fail, but not every failed case means its requested patch operation failed.

| Operation | Tested | Success | Failure | Notes |
|---|---:|---:|---:|---|
| ADD | 4 | 4 semantic / 3 strict | 1 strict | Female code `F` versus display value `女` is evaluator-only |
| REMOVE | 1 | 0 | 1 | Gender filter remains |
| REPLACE | 3 | 2 | 1 | Customer level is not replaced; city replacement works |
| KEEP | 10 | Metric 10; time 9 | Time 1 | Q1 is incorrectly retained when changing to Q2 |
| CHANGE_METRIC | 2 | 2 | 0 | Works in current cases |
| CHANGE_TIME | 1 | 0 | 1 | Missing deterministic time replacement |
| CHANGE_ORDER | 0 | — | — | Not covered; no capability claim |
| CHANGE_LIMIT | 1 | 1 patch | 0 patch | Limit becomes 10, but readiness is incorrectly clarification |

The patch engine's general missing operations are target-keyed `REMOVE_FILTER`, time-range replacement, and compound filter replacement by semantic target. A separate clarification-state recomputation defect causes a correct `CHANGE_LIMIT` plan to fail. Parent metric retention is 10/10; context retention is not the primary problem.

## 9. Remaining hallucination failures

1. `HALL_AGENT_004` — “推荐最适合客户购买的具体基金”
   - Primary label: `unsupported misclassified`
   - Actual behavior: ready
   - Required behavior: unsupported or precise suitability clarification
   - No unregistered metric/dimension ID is invented; the failure is capability-boundary handling.

2. `HALL_AGENT_008` — “找出一定会购买产品的客户”
   - Primary label: `unsupported misclassified`
   - Secondary label: semantic concept injection
   - Actual behavior: ready with `product_entity` semantics
   - Required behavior: reject the unsupported predictive-certainty claim rather than reinterpret it as a product entity query.

Thus the remaining 10% is not registry-ID hallucination. It is unsupported intent being converted into an executable-looking supported intent.

## 10. Operator coverage: tested is not the same as supported

Reported covered operators (`5/16`):

- `between`, `eq`, `gt`, `gte`, `lt`

Reported uncovered operators:

- `contains`, `ends_with`, `exists`, `in`, `is_not_null`, `is_null`, `lte`, `neq`, `not_exists`, `not_in`, `starts_with`

Interpretation:

- Dataset/coverage gaps with registered Agent/Stage 4/SQL mappings: `neq`, `lte`, `in`, `not_in`, `contains`, `starts_with`, `ends_with`. Absence from this benchmark does not mean unsupported.
- `exists` is present in semantic entity Gold, but the coverage collector only walks plan filters; reported coverage understates actual test presence. Those entity cases fail before safe entity compilation.
- Partial end-to-end system gaps: `exists`, `not_exists`, `is_null`, and `is_not_null`. They exist in the Stage 4 schema; generic Agent parsing deliberately skips the no-value operators, and generic SQL compilation does not provide a complete entity `exists/not_exists` route.
- `CHANGE_ORDER` and several set/string/null operators need independent positive and negative cases before support can be claimed.

## 11. Repair priorities

### P0 — semantic correctness, generalization, and hallucination boundary

1. Adjudicate the 21 mixed MX cases before using them as ready-status evidence; independently fix exact registry-ID metric linking.
2. Fix explicit two-digit-year, quarter snapshot, and date-range parsing without inferring omitted time.
3. Fix typed metric/concept/dimension linking and prevent grouping markers from becoming filters.
4. Route controlled names through entity resolution; never guess IDs.
5. Stabilize coarse intent classification and reject suitability/predictive certainty before planning.

### P1 — SQL and multi-turn execution readiness

1. Add a registry-driven metric-expression compiler for aggregates such as `customer_count`.
2. Compile verified branch hierarchy joins and concept-to-dimension filters without bypassing guards.
3. Implement deterministic target-keyed remove/replace/time patches and recompute clarification after a valid patch.

### P2 — evaluator, canonicalization, and coverage reporting

1. Add semantic Plan canonicalization for implicit dimensions, enum code/display values, concept expansions, and redundant grouping markers.
2. Preserve genuinely different Boolean trees and snapshot semantics as non-equivalent.
3. Expand operator cases and fix coverage accounting for semantic expected operators.

The machine-readable priority list is in `failure_priority.csv`.

## 12. Staged repair route

### Stage 8.2 — Semantic Generalization Fix

- Root causes: typed metric/dimension/concept linking, entity resolution, time parsing, intent stability, unsupported routing.
- Modify: `agent/services/condition_grounder.py`, semantic retrieval/routing, `agent/services/entity_resolver.py`, time grounding, planner/clarification boundary checks, and metadata aliases only when generally justified.
- Do not modify: Stage 4 Gold plans, benchmark expected values for score chasing, SQL compiler, or official-Q&A-specific logic.
- Expected improvement: Semantic exact accuracy becomes representative after canonical evaluation; exact-ID recall, official time accuracy, entity accuracy, and hallucination handling improve.

### Stage 8.3 — Plan Canonicalization Fix

- Root causes: semantic equivalence not normalized, redundant grouping concepts, implicit customer dimension, enum code/display representation.
- Modify: benchmark-side semantic canonicalizer and `benchmark/evaluators/plan_evaluator.py`; report raw exact and canonical semantic match separately.
- Do not modify: Agent output merely to mirror Gold field shape; do not collapse different Boolean trees or quarter/snapshot meanings.
- Expected improvement: the 10 evaluation-only Query Plan failures stop depressing semantic-plan accuracy while the 20 true errors remain visible.

### Stage 8.4 — SQL Compiler Coverage Fix

- Root causes: aggregate metric expression compilation, branch hierarchy joins, concept filter compilation, supported grain coverage.
- Modify: `guardrail/sql_generator.py`, `guardrail/logical_planner.py`, verified join metadata, and a safe expression compiler.
- Do not modify: Stage 4 Validator, Schema Guard, Join Guard, Cost Guard, parameterization, or benchmark-specific templates.
- Expected improvement: the seven SQL-suite and five duplicate end-to-end failure rows are addressed by four reusable compiler capabilities.

### Stage 8.5 — Multi-turn Patch Fix

- Root causes: missing remove, time replace, compound target replace, and clarification recomputation.
- Modify: `agent/services/context_manager.py`, deterministic Plan Patch engine, and post-patch validation/clarification state derivation.
- Do not modify: parent plans in place, Stage 4 Validator, or rebuild every turn from an unconstrained planner.
- Expected improvement: REMOVE, CHANGE_TIME, customer-level REPLACE, and valid CHANGE_LIMIT completion become reliable while current 10/10 metric retention remains intact.

### Stage 8.6 — Re-benchmark

- Freeze the same 226 cases and rerun all suites after each approved fix.
- Gold changes require separate human adjudication, versioning, and rationale; they must not be bundled with code fixes.
- Report raw exact, canonical semantic, and adjudicated-status metrics side by side.
- Re-run Stage 4 regression, the full repository test suite, rule snapshot, and dry-run/real-DB boundary checks.

## 13. Final answers

1. All 105 failures are classified: **yes**.
2. REAL_SYSTEM_DEFECT: **55**.
3. EVALUATION_DEFECT: **27**.
4. AMBIGUOUS: **23**.
5. Top root causes: Gold mismatch, unnormalized semantic equivalence, time parsing, SQL metric compiler, plan normalization, plan semantic loss, metric/concept/entity linking, and intent classification.
6. Query Plan 0%: 20 real semantic errors + 3 structure-only + 7 canonicalization-only; defaults/order/output are not the cause.
7. Semantic 26.67%: 11 real defects and 11 evaluator-only failures among the 22 failures; exact-set scoring is too strict.
8. Generalization 10%: 21 mixed missing-time Gold conflicts dominate; two non-MX real defects remain, plus canonicalization ambiguity.
9. SQL 53.33%: primarily `customer_count` expression compilation, followed by safe joins, concept filters, and one unsupported grain.
10. Multi-turn 50%: remove/time/customer-level replacement and readiness recomputation; metric retention and metric replacement work.
11. Hallucination 90%: two unsupported predictive/suitability requests are misclassified as ready.
12. Operator coverage: seven clear dataset gaps, four partial end-to-end support gaps, and one coverage-accounting defect around `exists`.
13. P0/P1/P2 actions are listed above and in the CSV.
14. Next modules: semantic grounding/entity/time/router first, canonical evaluator second, SQL compiler third, deterministic patch engine fourth, then frozen re-benchmark.
