# Stage 8.2 — Semantic Generalization Fix Report

## 1. Scope and constraints

This change fixes only the P0 semantic root causes identified by Stage 8.1:

- `TIME_PARSING`
- `ENTITY_RESOLUTION`
- `SEMANTIC_METRIC_LINKING`
- `SEMANTIC_DIMENSION_LINKING`
- `SEMANTIC_CONCEPT_LINKING`
- `INTENT_CLASSIFICATION`
- `CLARIFICATION_ERROR`
- `UNSUPPORTED_HANDLING`

No SQL Compiler, Plan Canonicalization Evaluator, Multi-turn Patch Engine, Benchmark expected/case, Stage 6 Guardrail, or Stage 7 Marketing rule was changed. No branch uses a benchmark case ID or a complete benchmark query.

## 2. Files

### Added

- `agent/services/time_parser.py`
- `metadata/semantic_boundaries.yaml`
- `tests/agent/test_stage82_semantic_generalization.py`
- `docs/stage8_2_semantic_fix_report.md`
- `benchmark/reports/stage8_2_semantic_fix/` (new run outputs; `stage8_final` is preserved)

### Modified

- `agent/models/grounded_condition.py`
- `agent/services/condition_grounder.py`
- `agent/services/semantic_retriever.py`
- `agent/services/entity_resolver.py`
- `agent/tools/entity_tool.py`
- `agent/planner.py`
- `agent/clarification.py`
- `agent/orchestrator.py`
- `metadata/agent_language.yaml`
- `metadata/metric_aliases.yaml`
- `metadata/concept_aliases.yaml`
- `metadata/segment_rules.yaml`

## 3. Grounding architecture changes

Grounding remains condition-level and typed. Phrases are classified before lookup, and the types now include `prediction_request`, `suitability_request`, and `unsupported_attribute` in addition to metric, dimension, concept, entity, time, operator, and value.

Precision changes include:

- exact Metric IDs participate in the metric catalog;
- `customer` and `product` nouns are treated as subjects unless an explicit grouping phrase such as “按客户” is present;
- generic dimension/entity dictionary entries no longer become fake concept filters;
- non-configurable segment rules expand through `segment_rules.yaml` into registered metric conditions;
- age ranges and threshold expressions ground to the registered `age` dimension;
- raw Metric IDs without time fail closed, except for explicitly non-temporal metrics;
- product category queries retain registered concept semantics, while metric + category phrases remain metric-scoped rather than becoming entities.

## 4. Time Parser

The new `TimeParser` supports:

- absolute Chinese and ISO dates;
- Chinese/ISO date ranges, including two-digit years;
- months, quarters (Q notation and Chinese notation), and years;
- month ranges such as `2026年1月至3月`;
- relative periods such as last N days/months and current/previous month/quarter;
- `start_of_period` / `end_of_period` wrappers.

Relative dates require a reliable `reference_date`, `context_date`, or `current_date`. Otherwise the result is a precise clarification. Time modifiers bind only to the adjacent time expression, preventing a later “Q1末” from changing an earlier ordinary Q1.

## 5. Entity Resolver

- Dataset exact mentions are considered before fuzzy resolution.
- Contained shorter entity codes are pruned when a longer exact identifier is present.
- Metric spans take priority over product entities, so “股票交易额” does not become a product entity.
- Product holding/trading relations are inferred from both prefixes and suffixes.
- Specific resolved entities suppress overlapping generic dimension/unmatched conditions.
- Product category, branch, and parent-branch relation targets are typed.
- Only `resolved` entities enter a ready plan; `ambiguous` and `not_found` remain fail closed.
- Missing customer identifiers never produce a guessed customer ID.

## 6. Unsupported boundaries

`metadata/semantic_boundaries.yaml` defines token-level, reusable patterns for:

- prediction requests (`UNSUPPORTED_PREDICTION`);
- product suitability/recommendation (`SUITABILITY_DATA_REQUIRED`);
- unsupported customer attributes (`UNSUPPORTED_ATTRIBUTE`).

These conditions produce `unsupported` with a reason and safe alternatives. They do not fall through to ordinary `entity_lookup` or customer filtering.

## 7. Clarification quality

Clarifications now identify the missing/unsupported semantic item, state why execution cannot continue, and tell the user what to provide or which registered alternatives are safe. Missing-time messages name the affected metric and accepted time formats.

## 8. Tests added

One new file adds 20 pytest instances across the 16 required categories:

1. subject customer is not a dimension;
2. customer-count synonyms;
3. metric + product category;
4. true product entity;
5. ambiguous entity;
6. nonexistent entity;
7. absolute date;
8. month;
9. quarter;
10. relative time;
11. missing required time (including raw Metric ID);
12. prediction request;
13. suitability request;
14. unsupported attribute;
15. fake concept prevention;
16. low-confidence clarification.

## 9. Regression results

- Stage 3 dictionary validation: passed.
- Stage 4 fixed Query Plan cases: **132/132 passed**.
- Stage 5 Agent tests: **46/46 passed**.
- Stage 6 Guardrail tests: **22/22 passed**.
- Stage 7 Marketing tests: **24/24 passed**.
- Full pytest: **109/109 passed**.

## 10. Benchmark Before → After

| Metric | Before (`stage8_final`) | After (`stage8_2_semantic_fix`) |
|---|---:|---:|
| Overall passed | 121/226 | 157/226 |
| Overall accuracy | 53.54% | 69.47% |
| Semantic Accuracy | 26.67% | 83.33% |
| Semantic component mean score | 82.44% | 93.11% |
| Hallucination Accuracy | 90.00% | 100.00% |
| Semantic Hallucination Rate | 0.00% | 0.00% |
| Generalization Strict Match | 10.00% | 30.00% |
| Generalization Component F1 | 70.45% | 87.27% |
| Unsupported Handling Accuracy | 90.00% | 100.00% |
| Entity Resolution F1 | 83.33% | 83.33% |
| Time Parsing Accuracy | 100.00% | 100.00% |

Additional semantic component improvements:

- Dimension F1: 59.33% → 93.33%
- Operator F1: 73.33% → 93.33%
- Intent Accuracy: 86.67% → 96.67%

The benchmark time metric was already saturated, so it does not reflect the newly added date/range/two-digit-year/relative-time coverage.

## 11. Remaining Semantic cases

The five remaining semantic failures are entity Gold/data conflicts, not newly hallucinated semantics:

- `SEM_E001`: real `dim_product` resolves 贵州茅台 to `9900269727`; Gold expects synthetic `P_GZM`.
- `SEM_E004`: `南京中心营业部` is not present in the real branch dataset; system returns `not_found`, while Gold expects `B_NJ001`.
- `SEM_E005`: `江苏分公司` has no exact real record and fuzzy candidates are tied; system clarifies, while Gold expects `PB_JS`.
- `SEM_E006`: the query supplies no customer identifier; system asks for one, while Gold guesses `C00000000000169`.
- `SEM_E009`: the real category source has no `CAT_FUND`; system uses the resolved registered category name `开放式基金`.

None of `P_GZM`, `B_NJ001`, `PB_JS`, `C00000000000169`, or `CAT_FUND` exists in the project CSV registries.

## 12. GOLD_POLICY_CONFLICT

All 21 `GEN_MX100`–`GEN_MX120` queries omit time while Gold injects `2026 Q1` and expects ready. The final implementation links every raw Metric ID but returns:

- `status = needs_clarification`
- `time_range = null`

These 21 cases remain strict-match failures by design and are classified as `GOLD_POLICY_CONFLICT`, not repair failures. No time value is inferred from Benchmark Gold.

## 13. Hallucination and compatibility conclusion

- No new semantic hallucination was introduced; the measured rate remains 0%.
- Hallucination suite improved to 20/20.
- Guardrail, Marketing, Stage 4, and full pytest remain fully passing.
- Overall Benchmark failures dropped from 105 to 69 despite retaining all 21 low-hallucination policy conflicts.

## 14. Stage 8.3 readiness

Stage 8.2 has met its success criteria: P0 semantic failures dropped materially, typed time/entity boundaries are stricter, unsupported prediction/suitability requests fail closed, and frozen capabilities remain intact. The project can proceed to Stage 8.3, with the five entity Gold/data conflicts and 21 MX policy conflicts carried as explicit adjudication items rather than “fixed” through synthetic IDs or hidden time defaults.
