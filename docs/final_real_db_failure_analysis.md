# Final Real-DB Failure Root Cause Freeze

This analysis freezes the first 40-case run (18 correct, 22 failed). It is evidence for generic remediation only; Frozen Gold, queries, difficulty, and case IDs remain unchanged.

| Case | Failure | Primary root cause | Secondary root cause | Affected module | Scope | Recommended generic fix |
|---|---|---|---|---|---|---|
| RDB_S01 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | RESULT_NORMALIZATION | semantic value mapping / SQL compiler | generic | Resolve city aliases to a canonical semantic value and bind its DB storage value. |
| RDB_S02 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | RESULT_NORMALIZATION | semantic value mapping / SQL compiler | generic | Apply the same registered city normalization pipeline. |
| RDB_S03 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | RESULT_NORMALIZATION | semantic value mapping / SQL compiler | generic | Normalize gender aliases and bind the registered code. |
| RDB_S09 | RESULT_MISMATCH | METRIC_AGGREGATION | OUTPUT_SHAPE | intent/planner / SQL compiler | generic | Questions asking “是多少” must preserve aggregate metric intent instead of introducing a positive-value selection filter. |
| RDB_S12 | SQL_COMPILE_ERROR | TIME_END_OF_PERIOD | SQL_UNSUPPORTED_COMBINATION | time compiler / SQL compiler | generic | Compile period end using the metric fact's maximum available date not after requested end. |
| RDB_M01 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | METRIC_AGGREGATION | value mapping / SQL compiler | generic | Bind canonical city storage value before aggregate execution. |
| RDB_M02 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | RESULT_NORMALIZATION | value mapping / SQL compiler | generic | Normalize both city and gender through dimension metadata. |
| RDB_M06 | GUARDRAIL_BLOCK | EXISTS_GUARDRAIL_CONTRACT | ENUM_VALUE_NORMALIZATION | SQL AST / security guard / join guard | generic | Recognize validated correlated EXISTS and normalize dimension values without relaxing unknown relations. |
| RDB_M07 | GUARDRAIL_BLOCK | EXISTS_GUARDRAIL_CONTRACT | ENUM_VALUE_NORMALIZATION | SQL AST / security guard / join guard | generic | Recognize validated NOT EXISTS and preserve relation validation. |
| RDB_M08 | GUARDRAIL_BLOCK | EXISTS_GUARDRAIL_CONTRACT | TIME_END_OF_PERIOD | security guard / time compiler | generic | Accept safe correlated product EXISTS and apply holding metric's period-end contract. |
| RDB_M11 | RANKING_MISMATCH | OUTPUT_SHAPE | RANKING_ORDER | planner / SQL compiler | generic | Ranking must emit entity key plus metric, ordered by metric then stable key. |
| RDB_M12 | RANKING_MISMATCH | OUTPUT_SHAPE | RANKING_ORDER | planner / SQL compiler | generic | Apply the shared ranking result-shape contract. |
| RDB_M13 | SQL_COMPILE_ERROR | TIME_MONTH_BUCKET | SQL_UNSUPPORTED_COMBINATION | time-series compiler | generic | Derive registered month buckets from the metric fact date and group/order by the bucket. |
| RDB_C01 | COST_BLOCK | JOIN_COST_EXPLOSION | JOIN_GRAIN | SQL compiler / cost guard | generic | Push filters and thresholds into one-row-per-customer CTEs and deduplicate product dimension keys. |
| RDB_C02 | COST_BLOCK | JOIN_COST_EXPLOSION | JOIN_GRAIN | SQL compiler / cost guard | generic | Pre-aggregate facts and semi-join a deduplicated filtered product set. |
| RDB_C04 | RESULT_MISMATCH | ENUM_VALUE_NORMALIZATION | METRIC_AGGREGATION | value mapping / SQL compiler | generic | Normalize city before producing the multi-metric aggregate row. |
| RDB_C05 | COST_BLOCK | JOIN_COST_EXPLOSION | JOIN_GRAIN | SQL compiler / cost guard | generic | Push branch and product filters before aggregation; avoid many-to-many dimension expansion. |
| RDB_C08 | GUARDRAIL_BLOCK | OTHER | EXISTS_GUARDRAIL_CONTRACT | semantic negation / SQL guard | generic | Preserve negative holding polarity as NOT EXISTS and validate the correlated relation. |
| RDB_C09 | RESULT_MISMATCH | HAVING_PLACEMENT | METRIC_AGGREGATION | planner / SQL compiler | generic | Classify aggregate predicates from metric metadata and emit HAVING or outer filtering after aggregation. |
| RDB_C10 | RANKING_MISMATCH | OUTPUT_SHAPE | RANKING_ORDER | planner / SQL compiler | generic | Emit customer ID and per-customer metric, then deterministic metric/key ordering. |
| RDB_C11 | RESULT_MISMATCH | METRIC_AGGREGATION | OUTPUT_SHAPE | intent/planner / SQL compiler | generic | Do not turn a requested metric into an implicit `> 0` filter; aggregate all requested metrics to the requested scope. |
| RDB_C12 | SQL_COMPILE_ERROR | TIME_END_OF_PERIOD | ENUM_VALUE_NORMALIZATION | time compiler / value mapping | generic | Resolve the fact's effective period-end date and bind canonical dimension storage values. |

## Distribution

Primary causes: ENUM_VALUE_NORMALIZATION 6; OUTPUT_SHAPE 3; EXISTS_GUARDRAIL_CONTRACT 3; JOIN_COST_EXPLOSION 3; TIME_END_OF_PERIOD 2; METRIC_AGGREGATION 2; TIME_MONTH_BUCKET 1; HAVING_PLACEMENT 1; OTHER 1.

Every recommended change is a shared contract or metadata-driven capability. No case-specific branch is authorized.
