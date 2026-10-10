# Final Benchmark Summary

## Evaluation layers

Dry-run Benchmark and Real DB Benchmark answer different questions and must not be mixed.

| Benchmark | Database execution | Purpose |
|---|---|---|
| Stage 8 Frozen Dry-run | No | Semantic, plan, compiler, Guardrail, marketing, hallucination, coverage, and stability |
| Frozen Real DB | Yes, read-only MySQL | Full natural-language-to-result equivalence against independently reviewed Gold |

## Dry-run Frozen Benchmark

- Cases: 226
- Raw: 172/226 = **76.11%**
- Human-adjudicated: 206/226 = **91.15%**
- Raw semantic accuracy: **83.33%**
- SQL compile success: **93.33%**
- Guardrail unsafe block rate: **100%**
- Hallucination/unsupported handling: **100%** on 20 cases
- Marketing: **32/32 = 100%**
- Multi-turn: **80.00%**
- Stability: **100%** on the frozen stability set

Adjudicated accuracy is a policy-conflict review metric, not Real DB execution accuracy.

## Real DB Frozen Benchmark

Gold contains 40 independently reviewed cases: Simple 12, Medium 16, Complex 12. The frozen dataset SHA-256 remained:

`602496D8308DD391F4184F2A63A256E6942AF21F3FE3A1D6111987B3EAEB4FCD`

| Metric | First Frozen | Second Frozen |
|---|---:|---:|
| SQL execution success | 30/40 = 75.00% | 36/40 = 90.00% |
| Scalar | 10/19 = 52.63% | 19/19 = 100.00% |
| Set | 5/11 = 45.45% | 8/11 = 72.73% |
| Grouped | 3/6 = 50.00% | 5/6 = 83.33% |
| Ranking | 0/3 = 0.00% | 3/3 = 100.00% |
| Time Series | 0/1 = 0.00% | 1/1 = 100.00% |
| Result equivalence | 18/40 = 45.00% | 36/40 = 90.00% |
| Final execution accuracy | **18/40 = 45.00%** | **36/40 = 90.00%** |
| Failures | 22 | 4 |

The improvement came from generic enum normalization, aggregation/output-shape contracts, HAVING placement, time and time-series compilation, EXISTS contract alignment, cost-aware semi-joins/filter pushdown, ranking, result normalization, and loader isolation. Frozen Gold was not changed to match Agent output.

## Remaining failures

`RDB_M06`, `RDB_M07`, `RDB_C01`, and `RDB_C11` remain Benchmark failures. All four were blocked by the unchanged Cost Guard after EXPLAIN; they were not force-executed and are not counted as correct.

Cost optimization focused on query structure rather than raising the safety threshold:

| Case | Before estimated rows | After estimated rows | Final status |
|---|---:|---:|---|
| RDB_C01 | 18,362,885,064 | 2,545,682 | COST_BLOCK |
| RDB_C02 | 159,280,285 | 504,685 | PASS |
| RDB_C05 | 29,219,610 | 475,306 | PASS |

Applied patterns included deduplicated semi-joins, pre-aggregation, snapshot-date reduction, base-entity filtering, and fact-filter pushdown. The 1,000,000-row guard threshold remained unchanged.

## Latency

| Difficulty | Avg | P50 | P95 | Max |
|---|---:|---:|---:|---:|
| Simple | 3012.83 ms | 2834.13 ms | 4336.44 ms | 4336.44 ms |
| Medium | 3653.17 ms | 3343.93 ms | 7052.95 ms | 7052.95 ms |
| Complex | 4438.22 ms | 4398.21 ms | 6878.31 ms | 6878.31 ms |

All maxima are below 60 seconds. `MINUTE_LEVEL_REQUIREMENT = PASS`.

## Final gate

- No PASS → FAIL regression between Frozen runs.
- Current Python 241/241, Frontend 14/14, Frontend Build PASS. The immutable Second Frozen report retains its original 240-test snapshot; the additional test covers only release/deployment boundaries.
- Frontend REAL_DB E2E PASS.
- `NATURAL_LANGUAGE_FINAL_EXECUTION_ACCURACY_TARGET = PASS`.
- `AGENT_FINAL_READY = YES`.
