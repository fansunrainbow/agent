# Stage 8.3 — Plan Canonicalization Fix Report

## 1. Conclusion

Stage 8.3 is complete. The benchmark now reports strict structural equality and semantic canonical equality side by side, while production execution continues to use the validated original Query Plan. No benchmark expected value, Stage 8.2 semantic-grounding behavior, case ID rule, or fixed-query rule was changed.

Across `query_plan + generalization`, strict raw equality is **12/60 (20.00%)** and canonical semantic equality is **20/60 (33.33%)**. The gain is eight Query Plan cases whose business semantics are equal despite representational differences. No Generalization failure was hidden by canonicalization.

## 2. Files

### Added in Stage 8.3

- `query_plan/canonicalizer.py`
- `benchmark/evaluators/plan_equivalence.py`
- `tests/benchmark/test_plan_canonicalization.py`
- `docs/stage8_3_plan_canonicalization_report.md`
- `benchmark/reports/stage8_3_plan_canonicalization/`

### Modified in Stage 8.3

- `query_plan/__init__.py`
- `benchmark/evaluators/plan_evaluator.py`
- `benchmark/reports/report_writer.py`

The canonicalizer exposes the `CanonicalQueryPlan` comparison contract and is deterministic, side-effect free, LLM-free, query-text-free, and benchmark-case-ID-free.

## 3. Canonicalization rules

- Schema-empty lists (`null`, missing, or `[]`) become `[]` for list-valued semantic fields. Missing/null time becomes `null`. This does not merge fields for which absence and explicit emptiness carry different business meaning.
- Registry IDs are used directly for metrics and dimensions; display names, aliases, and raw phrases are not comparison keys.
- `metrics`, `dimensions`, `entities`, `group_by`, assumptions, ambiguities, and set-valued filter operands are deterministically ordered. `order_by` and `between` bounds retain their original order.
- Numeric strings and integral floats share a stable numeric representation. Percentage conversion is enabled only when metadata proves that the target metric is a ratio.
- Operator aliases such as `>`, `>=`, `<`, `<=`, `=`, and `!=` map to registry operators. Negative operators retain negation semantics through an explicit `NOT` node.
- Subject and dimensions remain independent; the canonicalizer never inserts a subject into dimensions.
- Intent and status values are not coalesced. In particular, `ready`, `needs_clarification`, `invalid`, and any unsupported state remain different.

## 4. Semantic exact-match field policy

| Policy | Fields | Behavior |
|---|---|---|
| Core semantic comparison | `status`, `intent`, `subject`, `metrics`, `dimensions`, `filters`, `entities`, `time_range`, `group_by`, `having`, `order_by`, `limit` | Always compared after safe canonicalization, including when Gold omits the field. |
| Semantic subfields | `assumptions`, `ambiguities` | Compared through stable semantic subfields when present in the expected contract; extra values are reported but do not retroactively expand an old Gold contract. |
| Presentation-only | `output` | Canonicalized for audit and reported as ignored; it does not change execution semantics. |
| Explicitly ignored | `version`, `confidence`, `context` | Reported as policy-ignored; they are schema/versioning, probabilistic, or conversation provenance rather than plan execution semantics. |

Strict raw equality still compares the complete original JSON, so presentation/default differences remain visible even when canonical equality ignores them.

## 5. Filter canonicalization

Filter leaves are normalized recursively. `AND` and `OR` children are canonicalized, same-operator nesting is flattened, and commutative children are sorted by a stable JSON semantic key. Mixed `AND`/`OR` trees are not flattened, and `NOT` structure is preserved. Top-level filter arrays are treated as an implicit conjunction.

Membership operands for `in/not_in` are unordered sets. Positional operands are not sorted: notably, `between [10, 20]` is deliberately different from `between [20, 10]`. Concept expansion occurs only through metadata-backed concept-to-dimension/value mappings.

## 6. Time canonicalization

Metadata/parser-proven quarter, month, year, absolute-date, and date-range forms become an interval with stable start/end dates and granularity. A full calendar quarter date range is equivalent to that quarter. `raw_expression` is preserved in the production plan but excluded from canonical comparison. Snapshot forms such as `start_of_period` and `end_of_period` retain their type and are not equated with a full interval.

## 7. Entity canonicalization

Resolved entities compare by `entity_type + resolution_status + canonical resolved ID`; surface text, display name, confidence, source, and attributes do not determine equality. Ambiguous entities compare their candidate IDs, while `not_found` retains its normalized surface. Resolved, ambiguous, and not-found states can never compare equal merely because their text is similar.

## 8. Gold Schema Mismatch classification

No Gold was edited. The 23 cases originally classified with primary root cause `GOLD_SCHEMA_MISMATCH` divide into:

- **21 Gold policy/time conflicts** (`GEN_MX100`–`GEN_MX120`): the query omits time, while Gold injects 2026 Q1 and `ready`. The canonical evaluator correctly keeps these unequal rather than masking status/time semantics.
- **2 ambiguous Gold semantic specifications** (`OFFICIAL_002`, `OFFICIAL_004`): custom age bands and the implied `customer_count` metric require human adjudication; canonicalization cannot decide them.
- **0 confirmed old-schema-only cases** and **0 confirmed missing-field-only cases** in that 23-case cluster.

Separately, the five Stage 8.2 residual entity cases use synthetic or registry-incompatible entity IDs (`SEM_E001`, `SEM_E004`, `SEM_E005`, `SEM_E006`, `SEM_E009`). They remain metadata/data conflicts and are not canonicalized to real resolved IDs. Thus `GOLD_DATA_CONFLICT` is not hidden.

## 9. Tests

The canonicalization suite contains **22 tests**, covering all 20 requested scenarios plus two ordering boundary cases (`in` reorder is equivalent; reversed `between` bounds are not). The combined canonicalization/benchmark test selection passes **27/27**.

Regression results:

- Stage 4 Query Plan: **12/12**
- Agent/Stage 5 including Stage 8.2 semantic tests: **46/46**
- Stage 6 Guardrail: **22/22**
- Stage 7 Marketing: **24/24**
- Full repository test collection: **131/131**
- Rule snapshot: **PASS**

The current repository collects fewer Stage 4 tests than the historical Stage 8.2 report; counts above are the actual current collection and are not presented as the same historical test inventory.

## 10. Benchmark before/after

`Raw` and `Canonical` were introduced only in Stage 8.3. Earlier reports exposed `plan_exact_match`, which was a legacy normalized comparison rather than strict raw JSON equality. Historical values are therefore shown in their real column and are not relabeled or backfilled.

| Metric | Before Stage 8.2 (`stage8_final`) | After Stage 8.2 | After Stage 8.3 |
|---|---:|---:|---:|
| Query Plan strict raw exact | not measured | not measured | **16.67% (5/30)** |
| Query Plan canonical exact | not measured | not measured | **43.33% (13/30)** |
| Query Plan legacy normalized exact | 0.00% | 43.33% | 43.33% |
| Query Plan component F1 | 80.87% | 91.78% | **91.78%** |
| Generalization strict raw exact | not measured | not measured | **23.33% (7/30)** |
| Generalization canonical exact | not measured | not measured | **23.33% (7/30)** |
| Generalization legacy normalized exact | 10.00% | 30.00% | 30.00% |
| Generalization component F1 | 70.45% | 87.27% | **87.27%** |
| Semantic accuracy | 26.67% | 83.33% | **83.33%** |
| Hallucination | 18/20 | 20/20 | **20/20** |
| Total benchmark passed | 121/226 | 157/226 | **155/226** |
| Failure count | 105 | 69 | **71** |

The two-case total-pass decrease is intentional evaluator correction, not a production regression: `GEN_X008` and `GEN_X009` have `subject=customer` in Gold and `subject=product` in the actual plan. The old evaluator omitted `subject`; Stage 8.3 is required to compare it independently from dimensions. Semantic accuracy and both component F1 values did not decline.

## 11. Remaining errors and next stage

The targeted suites retain **19 real Plan semantic errors** after excluding the 21 Generalization Gold policy/time conflicts: 17 in `query_plan` and two subject mismatches in `generalization`. They involve real status, time, filter, intent, or subject differences and must not be removed by canonicalization.

Stage 8.3 meets its safety goal: eight structurally different Query Plans are now recognized as semantically equal, all core business fields remain enforced, Semantic accuracy is unchanged, Hallucination remains 20/20, and regression tests pass. The project can proceed to **Stage 8.4 — SQL Compiler Coverage Fix**, while the 21 Gold policy conflicts and ambiguous/synthetic Gold items remain explicitly queued for separate human adjudication.

## 12. Evidence

- Full report: `benchmark/reports/stage8_3_plan_canonicalization/benchmark_report.json`
- Reviewer report: `benchmark/reports/stage8_3_plan_canonicalization/benchmark_report.md`
- Per-plan equivalence evidence: `benchmark/reports/stage8_3_plan_canonicalization/plan_equivalence_cases.jsonl`
- Targeted report: `benchmark/reports/stage8_3_plan_canonicalization/targeted/benchmark_report.json`
- Targeted equivalence evidence: `benchmark/reports/stage8_3_plan_canonicalization/targeted/plan_equivalence_cases.jsonl`
